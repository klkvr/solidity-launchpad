// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "@openzeppelin/contracts/mocks/ERC20Mock.sol";

contract MockERC20 is ERC20Mock {
    constructor(address deployer) ERC20Mock("TestUSDT", "TUSDT",deployer, 0){}
}
