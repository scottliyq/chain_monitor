Concrete_STABLE = "0x6503de9FE77d256d9d823f2D335Ce83EcE9E153f"
TOKEN_STABLE= "0x6cc3e0d6cc519678b5152cf9990184fe43846d44"

# 代币合约地址定义（按链分类）
TOKEN_CONTRACTS = {
    # Ethereum Mainnet (Chain ID: 1)
    "ethereum": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86a33E6441b57ee3e4BEd34CE66fcEe8d5c4",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    },
    
    # Arbitrum One (Chain ID: 42161)
    "arbitrum": {
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # USDC.e (native)
        "USDC.e": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",  # USDC (bridged)
        "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
    },
    
    # Base (Chain ID: 8453)
    "base": {
        "USDT": "0x0000000000000000000000000000000000000000",  # Base没有原生USDT
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # Native USDC
        "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",  # Bridged USD Coin
        "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        "WETH": "0x4200000000000000000000000000000000000006",
        "CBETH": "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",
    },
    
    # BSC (Chain ID: 56)
    "bsc": {
        "USDT": "0x55d398326f99059fF775485246999027B3197955",  # Tether USD
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",  # USD Coin
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",  # Binance USD (deprecated)
        "DAI": "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
        "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "BNB": "0x0000000000000000000000000000000000000000",  # Native BNB
    }
}

# 快速访问主网代币（保持向后兼容）
USDT_CONTRACT_ADDRESS = TOKEN_CONTRACTS["ethereum"]["USDT"]
USDC_CONTRACT_ADDRESS = TOKEN_CONTRACTS["ethereum"]["USDC"]

# 获取指定链的代币地址的辅助函数
def get_token_address(chain: str, token: str) -> str:
    """
    获取指定链上的代币合约地址
    
    Args:
        chain (str): 链名称 ("ethereum", "arbitrum", "base", "bsc")
        token (str): 代币符号 ("USDT", "USDC", "DAI", 等)
        
    Returns:
        str: 合约地址，如果未找到返回空字符串
    """
    return TOKEN_CONTRACTS.get(chain, {}).get(token, "")

def get_all_usdt_addresses() -> dict:
    """获取所有链上的USDT地址"""
    usdt_addresses = {}
    for chain, tokens in TOKEN_CONTRACTS.items():
        if "USDT" in tokens and tokens["USDT"] != "0x0000000000000000000000000000000000000000":
            usdt_addresses[chain] = tokens["USDT"]
    return usdt_addresses

def get_all_usdc_addresses() -> dict:
    """获取所有链上的USDC地址"""
    usdc_addresses = {}
    for chain, tokens in TOKEN_CONTRACTS.items():
        for token_name, address in tokens.items():
            if "USDC" in token_name and address != "0x0000000000000000000000000000000000000000":
                usdc_addresses[f"{chain}_{token_name}"] = address
    return usdc_addresses

# 已知的合约类型映射（用于识别合约类型）
KNOWN_CONTRACTS = {
    # Uniswap V3 Pools
    "0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36": "UniswapV3Pool",
    "0x11b815efB8f581194ae79006d24E0d814B7697F6": "UniswapV3Pool", 
    "0xc7bBeC68d12a0d1830360F8Ec58fA599bA1b0e9b": "UniswapV3Pool",
    "0x33676385160f9d8f03a0db2821029882f7c79e93": "UniswapV3Pool",
    
    # Aave V3
    "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2": "AaveV3Pool",
    "0x794a61358D6845594F94dc1DB02A252b5b4814aD": "AaveV3Pool",
    
    # Compound V3
    "0xc3d688B66703497DAA19211EEdff47f25384cdc3": "CompoundV3",
    "0xA17581A9E3356d9A858b789D68B4d866e593aE94": "CompoundV3",
    
    # Curve Finance
    "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7": "Curve3Pool",
    "0xA5407eAE9Ba41422680e2e00537571bcC53efBfD": "CurvePool",
    
    # CEX deposits
    "0x28C6c06298d514Db089934071355E5743bf21d60": "Binance",
    "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549": "Binance",
    "0xDFd5293D8e347dFe59E90eFd55b2956a1343963d": "Binance",
    "0x564286362092D8e7936f0549571a803B203aAceD": "Binance",
    "0x0681d8Db095565FE8A346fA0277bFfdE9C0eDBBF": "Binance",
    "0xF977814e90dA44bFA03b6295A0616a897441aceC": "Binance",
    "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3": "Binance",
    "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE": "Binance",
    
    # Coinbase
    "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3": "Coinbase",
    "0x503828976D22510aad0201ac7EC88293211D23Da": "Coinbase",
    "0xddfAbCdc4D8FfC6d5beaf154f18B778f892A0740": "Coinbase",
    "0x3cD751E6b0078Be393132286c442345e5DC49699": "Coinbase",
    
    # Other exchanges
    "0x6Cc5F688a315f3dC28A7781717a9A798a59fDA7b": "OKX",
    "0x2B5634C42055806a59e9107ED44D43c426E58258": "KuCoin",
    "0xE853c56864A2ebe4576a807D26Fdc4A0adA51919": "Kraken",
}