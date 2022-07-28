// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@pancakeswap/contracts/interfaces/IPancakeRouter02.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

contract Launchpad is AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;
    using ECDSA for bytes32;

    bytes32 public constant SIGNER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    struct PlacedToken {
        address owner;
        uint256 price; // in _pricingToken multiplied by 10 ** _decimals
        uint256 initialVolume;
        uint256 volume;
        uint256 collectedAmount; // in _pricingToken
        bool isActive;
    }

    IPancakeRouter02 pancakeSwap;

    mapping (uint256 => bool) public nonces;
    mapping (IERC20 => PlacedToken) public placedTokens;

    uint256 public collectedFees;

    uint256 internal _feePercent; 
    uint256 private _decimals = 18;
    IERC20 private _pricingToken;

    event TokenPlaced(IERC20 token, uint256 nonce);
    event RoundFinished(IERC20 token);
    event TokensBought(IERC20 token, address buyer, uint256 amount);
    event FundsCollected(IERC20 token);

    constructor(IERC20 pricingToken_, uint256 feePercent_, IPancakeRouter02 pancakeSwap_) {
        _feePercent = feePercent_;
        _pricingToken = pricingToken_;
        pancakeSwap = pancakeSwap_;
        _setRoleAdmin(SIGNER_ROLE, ADMIN_ROLE);
        _setRoleAdmin(ADMIN_ROLE, ADMIN_ROLE);

        _setupRole(ADMIN_ROLE, msg.sender);
        _setupRole(SIGNER_ROLE, msg.sender);
    }

    function feePercent() public view returns(uint256) {
        return _feePercent;
    }

    function decimals() public view returns(uint256) {
        return _decimals;
    }

    function setFeePercent(uint256 feePercent_) public onlyRole(ADMIN_ROLE) {
        _feePercent = feePercent_;
    }

    function pricingToken() public view returns(IERC20) {
        return _pricingToken;
    }

    function setPricingToken(IERC20 pricingToken_) public onlyRole(ADMIN_ROLE) {
        _pricingToken = pricingToken_;
    }

    function placeTokens(uint256 nonce, uint256 price, IERC20 token, uint256 initialVolume, bytes memory signature) public {
        address sender = msg.sender;

        require(!nonces[nonce], "Launchpad: Invalid nonce");
        require(!placedTokens[token].isActive, "Launchpad: This token was already placed");
        require(initialVolume > 0, "Launchpad: initial Volume must be >0");

        address signer = keccak256(abi.encodePacked(sender, address(token), initialVolume, price, nonce))
        .toEthSignedMessageHash().recover(signature);

        require(hasRole(SIGNER_ROLE, signer), "Launchpad: Invalid signature");
        
        token.safeTransferFrom(sender, address(this), initialVolume);

        placedTokens[token] = PlacedToken ({
                                            owner: sender,
                                            price: price,
                                            initialVolume: initialVolume,
                                            volume: initialVolume,
                                            collectedAmount: 0,
                                            isActive: true
                                        });
        
        nonces[nonce] = true;

        emit TokenPlaced(token, nonce);
    }

    function _sendCollectedFunds(address sender, IERC20 token) private {
        PlacedToken storage placedToken = placedTokens[token];
        require (sender == placedToken.owner, "Launchpad: You are not the owner of this token");

        _pricingToken.safeTransfer(placedToken.owner, placedToken.collectedAmount);
        placedToken.collectedAmount = 0;

        emit FundsCollected(token);
    }

    function getCollectedFunds(IERC20 token) public nonReentrant{
        _sendCollectedFunds(msg.sender, token);
    }

    function finishRound(IERC20 token) public nonReentrant {
        address sender = msg.sender;
        PlacedToken storage placedToken = placedTokens[token];

        require(sender == placedToken.owner, "Launchpad: You are not the owner of this token");

        _sendCollectedFunds(sender, token);
        
        token.safeTransfer(sender, placedToken.volume); 
        delete placedTokens[token];

        emit RoundFinished(token);
    }

    function getAmountByTokens(IERC20 token, IERC20 currency, uint256 tokensAmount) public view returns(uint256 amount){
        PlacedToken storage placedToken = placedTokens[token];
        amount = (tokensAmount * placedToken.price) / (10 ** _decimals);
        if (currency != _pricingToken) {
            address[] memory path = new address[](2);
            path[0] = address(currency);
            path[1] = address(_pricingToken);
            amount = pancakeSwap.getAmountsIn(tokensAmount * placedToken.price, path)[0];
        }
    }

    function getTokensByAmount(IERC20 token, IERC20 currency, uint256 amount) public view returns(uint256 tokensAmount){
        PlacedToken storage placedToken = placedTokens[token];
        if (currency == _pricingToken) {
            tokensAmount = (amount * (10 ** _decimals)) / placedToken.price;
        }
        else {
            address[] memory path = new address[](2);
            path[0] = address(currency);
            path[1] = address(_pricingToken);
            tokensAmount = (pancakeSwap.getAmountsOut(amount, path)[1] * (10 ** _decimals)) / placedToken.price;
        }
    }

    function buyTokens(IERC20 token, IERC20 paymentContract, uint256 volume) public nonReentrant {
        address sender = msg.sender;
        PlacedToken storage placedToken = placedTokens[token];

        require(placedToken.isActive == true, "Launchpad: Round isn't active");

        paymentContract.safeTransferFrom(sender, address(this), volume);

        if (paymentContract != _pricingToken) {
            address[] memory path = new address[](2);
            path[0] = address(paymentContract);
            path[1] = address(_pricingToken);
            paymentContract.approve(address(pancakeSwap), volume);
            volume = pancakeSwap.swapExactTokensForTokens(
                                                    volume,
                                                    0, 
                                                    path,
                                                    address(this),
                                                    block.timestamp + 100
                                                    )[1];
        }

        uint256 tokensAmount = (volume * (10 ** _decimals)) / placedToken.price;
        require(tokensAmount <= placedToken.volume, "Launchpad: Not enough volume");

        token.safeTransfer(sender, tokensAmount);

        uint256 fee = volume * _feePercent / 100;
        placedToken.collectedAmount += volume - fee;
        placedToken.volume -= tokensAmount;
        collectedFees += fee;

        emit TokensBought(token, sender, tokensAmount);
    }

    function withdrawFees() public onlyRole(ADMIN_ROLE) {
        _pricingToken.safeTransfer(msg.sender, collectedFees);
        collectedFees = 0;
    }
}

