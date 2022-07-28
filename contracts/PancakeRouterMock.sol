// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract PancakeRouterMock {
    function getAmountsOut(uint amountIn, address[] memory path)
        public
        view
        returns (uint[] memory amounts)
    {
        amounts = new uint[](path.length);
        amounts[0] = amountIn;
        for (uint256 i = 1; i < path.length; i++) {
            amounts[i] = 20;
        }
    }
    function getAmountsIn(uint amountOut, address[] memory path)
        public
        view
        returns (uint[] memory amounts)
    {
        amounts = new uint[](path.length);
        for (uint256 i = 0; i < path.length - 1; i++) {
            amounts[i] = 3;
        }
    }
    function swapExactTokensForTokens(
        uint amountIn,
        uint amounOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) public returns (uint[] memory amounts) {
        amounts = new uint[](path.length);
        amounts[0] = amountIn;
        amounts[1] = 20;
        IERC20(path[0]).transferFrom(msg.sender, address(this), amounts[0]);
        IERC20(path[1]).transfer(to, amounts[1]);
    }
}
