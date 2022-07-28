from brownie import accounts, Crypton, MockERC20, web3, PancakeRouterMock
from brownie.exceptions import VirtualMachineError
from eth_account.messages import encode_defunct
import brownie
import pytest

from dataclasses import dataclass
from typing import List

@dataclass
class PlacedToken:
        owner: str
        price: int
        initialVolume: int
        volume: int
        collectedAmount: int
        isActive: bool
    
        @classmethod
        def from_web3(cls, v):
            return cls(*v)

@pytest.fixture(scope="module")
def deployer():
    yield accounts.add()

@pytest.fixture(scope="module")
def user():
    yield accounts.add()

@pytest.fixture(scope="module")
def user2():
    yield accounts.add()

@pytest.fixture(scope="module")
def pancake_router(deployer, PancakeRouterMock):
    contract = deployer.deploy(PancakeRouterMock)
    yield contract

@pytest.fixture(scope="module")
def erc20(deployer, user2):
    contract = deployer.deploy(MockERC20, deployer)
    contract.mint(user2, 200, {"from": user2})
    yield contract

@pytest.fixture(scope="module")
def erc20_busd(deployer, user, user2, pancake_router):
    contract = deployer.deploy(MockERC20, deployer)
    contract.mint(user, 200, {"from": user})
    contract.mint(user2, 200, {"from": user2})
    contract.mint(pancake_router, 20, {"from": pancake_router})
    yield contract

@pytest.fixture(scope="module")
def erc20_other_token(deployer, user):
    contract = deployer.deploy(MockERC20, deployer)
    contract.mint(user, 200, {"from": user})
    yield contract

@pytest.fixture(scope="module")
def crypton(deployer, Crypton, erc20_busd, pancake_router):
    contract = deployer.deploy(Crypton, erc20_busd, 7, pancake_router)
    yield contract

@pytest.fixture(scope="module")
def SIGNER_ROLE(crypton):
    yield crypton.SIGNER_ROLE()

@pytest.fixture(scope="module")
def crypton_decimals(crypton):
    yield crypton.decimals()

def test_add_signer(deployer, user2, crypton, SIGNER_ROLE):
    assert crypton.hasRole(SIGNER_ROLE, deployer) == True
    crypton.grantRole(SIGNER_ROLE, user2, {"from": deployer})

    assert crypton.hasRole(SIGNER_ROLE, user2) == True

def test_remove_signer(deployer, user2, crypton, SIGNER_ROLE):
    crypton.revokeRole(SIGNER_ROLE, user2, {"from": deployer})

    assert crypton.hasRole(SIGNER_ROLE, user2) == False

def test_fee_percent_pricing_token(deployer, user, crypton, erc20_busd, erc20):
    assert crypton.feePercent({"from": user}) == 7
    assert crypton.pricingToken({"from": user}) == erc20_busd

    crypton.setFeePercent(8, {"from": deployer})
    assert crypton.feePercent({"from": user}) == 8
    crypton.setFeePercent(7, {"from": deployer})


    crypton.setPricingToken(erc20, {"from": deployer})
    assert crypton.pricingToken({"from": user}) == erc20
    crypton.setPricingToken(erc20_busd, {"from": deployer})

def test_place_token(deployer, user2, erc20, crypton, crypton_decimals):
    nonce = 1
    price = 2 * (10 ** crypton_decimals)
    token_address = erc20
    volume = 100

    user2_balance = erc20.balanceOf(user2)

    args = [str(user2), str(token_address), volume, price, nonce]
    h = web3.solidityKeccak(['address', 'address', 'uint256', 'uint256', 'uint256'], args)
    msg = encode_defunct(h)
    signed = web3.eth.account.sign_message(msg, deployer.private_key) 
    signature = signed.signature.hex()

    erc20.approve(crypton, user2_balance, {"from": user2})

    tx = crypton.placeTokens(nonce, price, token_address, volume, signature, {"from": user2})
    tokens = PlacedToken.from_web3(crypton.placedTokens(token_address))

    assert tx.events["TokenPlaced"]["token"] == erc20
    assert tx.events["TokenPlaced"]["nonce"] == nonce
    assert tokens.owner == user2
    assert tokens.initialVolume == 100
    assert tokens.volume == 100
    assert tokens.price == 2 * (10 ** crypton_decimals)
    assert tokens.collectedAmount == 0
    assert tokens.isActive == True

    assert crypton.nonces(nonce) == True

    assert erc20.balanceOf(crypton) == tokens.volume
    assert erc20.balanceOf(user2) == user2_balance - tokens.volume

    with pytest.raises(VirtualMachineError):
        erc20.approve(crypton, user2_balance, {"from": user2})

        crypton.placeTokens(nonce, price, token_address, volume, signature, {"from": user2})

    with pytest.raises(VirtualMachineError):
        nonce = 2

        user2_balance = erc20.balanceOf(user2)

        args = [str(user2), str(token_address), volume, price, nonce]
        h = web3.solidityKeccak(['address', 'address', 'uint256', 'uint256', 'uint256'], args)
        msg = encode_defunct(h)
        signed = web3.eth.account.sign_message(msg, deployer.private_key) 
        signature = signed.signature.hex()

        erc20.approve(crypton, user2_balance, {"from": user2})

        tx = crypton.placeTokens(nonce, price, token_address, volume, signature, {"from": user2})

def test_get_tokens_by_amount(crypton, user, erc20, erc20_other_token, erc20_busd):
    assert crypton.getTokensByAmount(erc20, erc20_busd, 10, {"from": user}) == 5
    assert crypton.getTokensByAmount(erc20, erc20_other_token, 10, {"from": user}) == 10

def test_get_tokens_by_amount(crypton, user, erc20, erc20_other_token, erc20_busd):
    assert crypton.getAmountByTokens(erc20, erc20_busd, 10, {"from": user}) == 20
    assert crypton.getAmountByTokens(erc20, erc20_other_token, 10, {"from": user}) == 3
    
    

def test_finish_round(user, user2, crypton, erc20):
    token_address = erc20
    user2_balance = erc20.balanceOf(user2)

    #omly tokens owner can finish the round
    with pytest.raises(VirtualMachineError):
        crypton.finishRound(token_address, {"from": user})
    
    tokens_before_finish = PlacedToken.from_web3(crypton.placedTokens(token_address))
    tx = crypton.finishRound(token_address, {"from": user2})
    tokens_after_finish =  PlacedToken.from_web3(crypton.placedTokens(token_address))
    assert tokens_after_finish.isActive == False
    assert tokens_after_finish.volume == 0
    assert tokens_after_finish.price == 0
    assert tokens_after_finish.collectedAmount == 0
    
    assert tx.events["RoundFinished"]["token"] == erc20
    # assert tokens_after_finish.volume == 0
    # assert tokens_after_finish.isActive == False
    assert erc20.balanceOf(crypton) == 0
    assert erc20.balanceOf(user2) == user2_balance + tokens_before_finish.volume

    # placedTokens deleted
    with pytest.raises(VirtualMachineError):
        crypton.finishRound(token_address, {"from": user2})


def test_buy_tokens(user, deployer, user2, erc20, erc20_busd, erc20_other_token, crypton, crypton_decimals):
    # place_start
    nonce = 2
    price = 2 * (10 ** crypton_decimals)
    token_address = erc20
    volume = 100

    user2_balance = erc20.balanceOf(user2)

    args = [str(user2), str(token_address), volume, price, nonce]
    h = web3.solidityKeccak(['address', 'address', 'uint256', 'uint256', 'uint256'], args)
    msg = encode_defunct(h)
    signed = web3.eth.account.sign_message(msg, deployer.private_key) 
    signature = signed.signature.hex()

    erc20.approve(crypton, user2_balance, {"from": user2})

    crypton.placeTokens(nonce, price, token_address, volume, signature, {"from": user2})
    tokens = PlacedToken.from_web3(crypton.placedTokens(token_address))
    # place_end
    # buy busd start
    token_address = erc20
    payment_contract = erc20_busd
    amount = 90
    cost = int(tokens.price / (10 ** crypton_decimals) * amount)
    feePercent = crypton.feePercent()

    tokens_volume_before_buy = tokens.volume

    user_busd_balance = erc20_busd.balanceOf(user)
    erc20_busd.increaseAllowance(crypton, user_busd_balance, {"from": user}) 

    # amount > volume
    with pytest.raises(VirtualMachineError):
        crypton.buyTokens(erc20, erc20_busd, 220, {"from": user})
    
    tx = crypton.buyTokens(token_address, payment_contract, cost, {"from": user})
    tokens = PlacedToken.from_web3(crypton.placedTokens(token_address))

    assert tx.events["TokensBought"]["token"] == erc20
    assert erc20_busd.balanceOf(crypton) == cost
    assert erc20_busd.balanceOf(user) == user_busd_balance - cost
    assert tokens.volume == tokens_volume_before_buy - amount
    assert erc20.balanceOf(crypton) == tokens_volume_before_buy - amount
    assert erc20.balanceOf(user) == amount
    assert crypton.collectedFees() == cost / 100 * feePercent
    collectedFees = crypton.collectedFees()

    ## get collected funds
    user2_busd_balance_before = erc20_busd.balanceOf(user2)
    crypton_busd_balance_before = erc20_busd.balanceOf(crypton)
    tx2 = crypton.getCollectedFunds(erc20, {"from": user2})

    assert tx2.events["FundsCollected"]["token"] == erc20
    assert erc20_busd.balanceOf(user2) == user2_busd_balance_before + tokens.collectedAmount
    assert erc20_busd.balanceOf(crypton) == crypton_busd_balance_before - tokens.collectedAmount
    ## get collected funds
    #buy busd end
    #buy with pancake start
    payment_contract = erc20_other_token
    amount = 10
    cost = int(tokens.price / (10 ** crypton_decimals) * amount)

    tokens_volume_before_buy = tokens.volume

    user_other_token_balance = erc20_other_token.balanceOf(user)
    crypton_busd_balance = erc20_busd.balanceOf(crypton)
    cost_in_other_token = 20

    
    erc20_other_token.increaseAllowance(crypton, cost_in_other_token, {"from":user}) 
    tx = crypton.buyTokens(token_address, payment_contract, cost_in_other_token, {"from": user})
    tokens = PlacedToken.from_web3(crypton.placedTokens(token_address))

    assert tx.events["TokensBought"]["token"] == erc20
    assert erc20_busd.balanceOf(crypton) == crypton_busd_balance + cost
    assert erc20_other_token.balanceOf(user) == user_other_token_balance - cost_in_other_token
    assert tokens.volume == 0
    assert crypton.collectedFees() == collectedFees +  cost / 100 * feePercent

def test_get_collected_funds(crypton, user, user2, erc20_busd, erc20):
    # only owner of tokens can withdraw money
    with pytest.raises(VirtualMachineError):
        crypton.getCollectedFunds(erc20, {"from": user})
    
    token_address = erc20
    user2_busd_balance_before = erc20_busd.balanceOf(user2)
    crypton_busd_balance_before = erc20_busd.balanceOf(crypton)
    tokens = PlacedToken.from_web3(crypton.placedTokens(token_address))

    tx = crypton.getCollectedFunds(erc20, {"from": user2})

    assert tx.events["FundsCollected"]["token"] == erc20
    assert erc20_busd.balanceOf(user2) == user2_busd_balance_before + tokens.collectedAmount
    assert erc20_busd.balanceOf(crypton) == crypton_busd_balance_before - tokens.collectedAmount
    assert tokens.initialVolume == 100

def test_withdraw_fees(crypton, deployer, erc20_busd):
    crypton.withdrawFees({"from": deployer})
    assert erc20_busd.balanceOf(deployer) == 13
    assert erc20_busd.balanceOf(crypton) == 0
