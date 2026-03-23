#!/usr/bin/env python3
"""
多链公共配置模块
统一维护网络元信息、浏览器 API 配置和 RPC 解析逻辑。
"""

import os


NETWORK_CONFIGS = {
    "ethereum": {
        "name": "Ethereum Mainnet",
        "chain_id": 1,
        "native_token": "ETH",
        "block_time": 12,
    },
    "arbitrum": {
        "name": "Arbitrum One",
        "chain_id": 42161,
        "native_token": "ETH",
        "block_time": 0.25,
    },
    "base": {
        "name": "Base",
        "chain_id": 8453,
        "native_token": "ETH",
        "block_time": 2,
    },
    "bsc": {
        "name": "BNB Smart Chain",
        "chain_id": 56,
        "native_token": "BNB",
        "block_time": 3,
    },
}

API_CONFIGS = {
    "ethereum": {
        "base_url": "https://api.etherscan.io/v2/api",
        "api_key_env": "ETHERSCAN_API_KEY",
        "chain_id": 1,
    },
    "arbitrum": {
        "base_url": "https://api.etherscan.io/v2/api",
        "api_key_env": "ARBISCAN_API_KEY",
        "chain_id": 42161,
    },
    "base": {
        "base_url": "https://api.etherscan.io/v2/api",
        "api_key_env": "BASESCAN_API_KEY",
        "chain_id": 8453,
    },
    "bsc": {
        "base_url": "https://api.etherscan.io/v2/api",
        "api_key_env": "BSCSCAN_API_KEY",
        "chain_id": 56,
    },
}

NETWORK_RPC_ENV = {
    "ethereum": "WEB3_RPC_URL",
    "arbitrum": "ARBITRUM_RPC_URL",
    "base": "BASE_RPC_URL",
    "bsc": "BSC_RPC_URL",
}

DEFAULT_RPCS = {
    "ethereum": "https://eth.llamarpc.com",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "base": "https://mainnet.base.org",
    "bsc": "https://bsc-dataseed1.binance.org",
}


def get_supported_networks() -> list[str]:
    """返回当前支持的网络列表。"""
    return list(NETWORK_CONFIGS.keys())


def get_network_config(network: str) -> dict:
    """获取网络基础配置。"""
    normalized_network = network.lower()
    if normalized_network not in NETWORK_CONFIGS:
        raise ValueError(
            f"不支持的网络: {network}. 支持的网络: {get_supported_networks()}"
        )
    return NETWORK_CONFIGS[normalized_network].copy()


def get_api_config(network: str) -> dict:
    """获取浏览器 API 配置，并自动回退到通用 Etherscan Key。"""
    normalized_network = network.lower()
    if normalized_network not in API_CONFIGS:
        raise ValueError(
            f"不支持的网络: {network}. 支持的网络: {get_supported_networks()}"
        )

    config = API_CONFIGS[normalized_network]
    api_key = os.getenv(config["api_key_env"]) or os.getenv(
        "ETHERSCAN_API_KEY", "YourApiKeyToken"
    )

    return {
        "base_url": config["base_url"],
        "api_key": api_key,
        "chain_id": config["chain_id"],
    }


def get_rpc_url(network: str, allow_default: bool = True) -> str:
    """获取网络 RPC URL。

    Args:
        network: 网络名称
        allow_default: 是否允许回退到公共默认 RPC
    """
    normalized_network = network.lower()
    if normalized_network not in NETWORK_RPC_ENV:
        raise ValueError(
            f"不支持的网络: {network}. 支持的网络: {get_supported_networks()}"
        )

    rpc_env_name = NETWORK_RPC_ENV[normalized_network]
    rpc_url = os.getenv(rpc_env_name) or os.getenv("WEB3_RPC_URL")

    if rpc_url:
        return rpc_url.strip()

    if allow_default:
        return DEFAULT_RPCS[normalized_network]

    raise ValueError(f"未找到 {rpc_env_name} 或 WEB3_RPC_URL 环境变量")
