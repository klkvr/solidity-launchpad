// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "@openzeppelin/contracts/mocks/ERC20Mock.sol";

contract MockERC20BUSD is ERC20Mock {
    constructor(address deployer) ERC20Mock("Test BUSD", "TBUSD",deployer, 0){}
}
