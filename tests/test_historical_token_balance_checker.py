#!/usr/bin/env python3
"""
历史代币余额查询工具测试类
测试单地址查询和批量查询功能
"""

import sys
import os
import unittest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from _path_setup import ensure_src_path

ensure_src_path()

from historical_token_balance_checker import HistoricalTokenBalanceChecker, setup_logging

class TestHistoricalTokenBalanceChecker(unittest.TestCase):
    """历史代币余额查询器测试类"""
    
    def setUp(self):
        """测试前的设置"""
        self.target_time = "2024-01-01 12:00:00"
        self.token = "USDT"
        self.network = "ethereum"
        self.test_address = "0x1234567890abcdef1234567890abcdef12345678"
        
        # 设置环境变量模拟
        self.env_patcher = patch.dict(os.environ, {
            'ETHERSCAN_API_KEY': 'test_api_key',
            'ETHEREUM_RPC_URL': 'https://test.rpc.url'
        })
        self.env_patcher.start()
        
        # 模拟日志设置
        self.logger = setup_logging()
    
    def tearDown(self):
        """测试后的清理"""
        self.env_patcher.stop()
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    def test_init_single_address_mode(self, mock_block_converter, mock_web3):
        """测试单地址模式初始化"""
        # 模拟依赖
        mock_web3_instance = Mock()
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.return_value = self.test_address
        
        mock_converter_instance = Mock()
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=self.test_address
        )
        
        # 验证初始化
        self.assertEqual(checker.target_time_str, self.target_time)
        self.assertEqual(checker.token, self.token.upper())
        self.assertEqual(checker.network, self.network.lower())
        self.assertEqual(checker.address_to_check, self.test_address)
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    def test_init_batch_mode(self, mock_block_converter, mock_web3):
        """测试批量模式初始化"""
        # 模拟依赖
        mock_web3_instance = Mock()
        mock_web3.return_value = mock_web3_instance
        
        mock_converter_instance = Mock()
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例（批量模式，不提供地址）
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=None
        )
        
        # 验证初始化
        self.assertEqual(checker.target_time_str, self.target_time)
        self.assertEqual(checker.token, self.token.upper())
        self.assertEqual(checker.network, self.network.lower())
        self.assertIsNone(checker.address_to_check)
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    def test_get_token_balance_for_address(self, mock_block_converter, mock_web3):
        """测试单个地址余额查询"""
        # 模拟Web3响应
        mock_web3_instance = Mock()
        mock_web3_instance.eth.call.return_value.hex.return_value = '0x000000000000000000000000000000000000000000000000000000e8d4a51000'  # 1000000000000 wei = 1,000,000 USDT
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.return_value = self.test_address
        
        mock_converter_instance = Mock()
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=self.test_address
        )
        
        # 测试余额查询
        result = checker.get_token_balance_for_address(self.test_address, 18000000)
        
        # 验证结果
        self.assertEqual(result['address'], self.test_address)
        self.assertEqual(result['balance_wei'], 1000000000000)
        self.assertEqual(float(result['balance_tokens']), 1000000.0)
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    def test_get_token_holders_from_events(self, mock_block_converter, mock_web3):
        """测试从事件获取代币持有人"""
        # 模拟Web3实例
        mock_web3_instance = Mock()
        
        # 模拟事件日志
        class MockHexString:
            def __init__(self, hex_value):
                self._hex = hex_value
            
            def hex(self):
                return self._hex
        
        mock_log1 = {
            'topics': [
                MockHexString('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'),  # Transfer事件签名
                MockHexString('0x0000000000000000000000000000000000000000000000000000000000000000'),  # from: 0x0 (铸币)
                MockHexString('0x000000000000000000000000' + self.test_address[2:].lower())  # to: test_address
            ]
        }
        
        mock_log2 = {
            'topics': [
                MockHexString('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'),
                MockHexString('0x000000000000000000000000' + self.test_address[2:].lower()),  # from: test_address
                MockHexString('0x000000000000000000000000abcdefabcdefabcdefabcdefabcdefabcdefabcd')   # to: another_address
            ]
        }
        
        mock_web3_instance.eth.get_logs.return_value = [mock_log1, mock_log2]
        mock_web3_instance.eth.block_number = 18000000
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.side_effect = lambda x: x.upper() if x else None
        
        mock_converter_instance = Mock()
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=None
        )
        
        # 测试获取持有人
        holders = checker.get_token_holders_from_events(from_block=0, to_block=18000000)
        
        # 验证结果
        self.assertIsInstance(holders, list)
        self.assertTrue(len(holders) >= 1)  # 至少应该有测试地址
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    def test_find_addresses_with_balance_above(self, mock_block_converter, mock_web3):
        """测试查找余额大于阈值的地址"""
        # 模拟Web3实例
        mock_web3_instance = Mock()
        mock_web3_instance.eth.call.return_value.hex.return_value = '0x000000000000000000000000000000000000000000000000000000e8d4a51000'  # 1,000,000 USDT
        
        # 创建模拟的事件日志
        class MockHexString:
            def __init__(self, hex_value):
                self._hex = hex_value
            
            def hex(self):
                return self._hex
        
        mock_web3_instance.eth.get_logs.return_value = [
            {
                'topics': [
                    MockHexString('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'),
                    MockHexString('0x0000000000000000000000000000000000000000000000000000000000000000'),
                    MockHexString('0x000000000000000000000000' + self.test_address[2:].lower())
                ]
            }
        ]
        mock_web3_instance.eth.block_number = 18000000
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.side_effect = lambda x: x.upper() if x else None
        
        mock_converter_instance = Mock()
        mock_converter_instance.get_block_number_by_timestamp.return_value = 18000000
        mock_converter_instance.get_block_by_timestamp.return_value = 18000000
        mock_converter_instance.datetime_to_timestamp.return_value = 1704110400  # 2024-01-01 12:00:00 UTC
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=None
        )
        
        # 测试查找大户
        min_balance = 500000.0  # 50万USDT
        results = checker.find_addresses_with_balance_above(min_balance, max_addresses=10)
        
        # 验证结果
        self.assertIsInstance(results, list)
        if results:  # 如果有结果
            self.assertTrue(all(r['balance_tokens'] >= min_balance for r in results))
            self.assertTrue(all('address' in r for r in results))
            self.assertTrue(all('balance_tokens' in r for r in results))
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    @patch('os.makedirs')
    @patch('builtins.open')
    def test_run_single_mode(self, mock_open, mock_makedirs, mock_block_converter, mock_web3):
        """测试单地址查询模式"""
        # 模拟文件操作
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # 模拟Web3
        mock_web3_instance = Mock()
        mock_web3_instance.eth.call.return_value.hex.return_value = '0x000000000000000000000000000000000000000000000000000000e8d4a51000'
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.return_value = self.test_address
        
        # 模拟区块转换器
        mock_converter_instance = Mock()
        mock_converter_instance.get_block_number_by_timestamp.return_value = 18000000
        mock_converter_instance.get_block_by_timestamp.return_value = 18000000
        mock_converter_instance.datetime_to_timestamp.return_value = 1704110400  # 2024-01-01 12:00:00 UTC
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=self.test_address
        )
        
        # 测试单地址查询
        result = checker.run(mode='single')
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertEqual(result['address'], self.test_address)
        self.assertIn('balance_tokens', result)
        self.assertIn('block_number', result)
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    @patch('os.makedirs')
    @patch('builtins.open')
    def test_run_batch_mode(self, mock_open, mock_makedirs, mock_block_converter, mock_web3):
        """测试批量查询模式"""
        # 模拟文件操作
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # 模拟Web3
        mock_web3_instance = Mock()
        mock_web3_instance.eth.call.return_value.hex.return_value = '0x000000000000000000000000000000000000000000000000000000e8d4a51000'
        mock_web3_instance.eth.get_logs.return_value = [
            {
                'topics': [
                    '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                    '0x0000000000000000000000000000000000000000000000000000000000000000',
                    '0x000000000000000000000000' + self.test_address[2:].lower()
                ]
            }
        ]
        mock_web3_instance.eth.block_number = 18000000
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.side_effect = lambda x: x.upper() if x else None
        
        # 模拟区块转换器
        mock_converter_instance = Mock()
        mock_converter_instance.get_block_number_by_timestamp.return_value = 18000000
        mock_converter_instance.get_block_by_timestamp.return_value = 18000000
        mock_converter_instance.datetime_to_timestamp.return_value = 1704110400  # 2024-01-01 12:00:00 UTC
        mock_block_converter.return_value = mock_converter_instance
        
        # 创建检查器实例
        checker = HistoricalTokenBalanceChecker(
            target_time=self.target_time,
            token=self.token,
            network=self.network,
            address_to_check=None
        )
        
        # 测试批量查询
        min_balance = 500000.0
        results = checker.run(mode='batch', min_balance=min_balance, max_addresses=10)
        
        # 验证结果
        self.assertIsInstance(results, list)
    
    def test_run_invalid_mode(self):
        """测试无效查询模式"""
        with patch('historical_token_balance_checker.Web3'), \
             patch('historical_token_balance_checker.BlockTimeConverter'):
            
            checker = HistoricalTokenBalanceChecker(
                target_time=self.target_time,
                token=self.token,
                network=self.network,
                address_to_check=self.test_address
            )
            
            # 测试无效模式
            with self.assertRaises(ValueError):
                checker.run(mode='invalid_mode')
    
    def test_run_single_mode_without_address(self):
        """测试单地址模式但未提供地址"""
        with patch('historical_token_balance_checker.Web3'), \
             patch('historical_token_balance_checker.BlockTimeConverter'):
            
            checker = HistoricalTokenBalanceChecker(
                target_time=self.target_time,
                token=self.token,
                network=self.network,
                address_to_check=None
            )
            
            # 测试单地址模式但未提供地址
            with self.assertRaises(ValueError):
                checker.run(mode='single')
    
    def test_run_batch_mode_without_min_balance(self):
        """测试批量模式但未提供最小余额"""
        with patch('historical_token_balance_checker.Web3'), \
             patch('historical_token_balance_checker.BlockTimeConverter'):
            
            checker = HistoricalTokenBalanceChecker(
                target_time=self.target_time,
                token=self.token,
                network=self.network,
                address_to_check=None
            )
            
            # 测试批量模式但未提供最小余额
            with self.assertRaises(ValueError):
                checker.run(mode='batch', min_balance=None)


class TestHistoricalTokenBalanceCheckerIntegration(unittest.TestCase):
    """集成测试类"""
    
    def setUp(self):
        """集成测试设置"""
        self.target_time = "2024-01-01 12:00:00"
        self.token = "USDT"
        self.network = "ethereum"
        self.test_address = "0x1234567890abcdef1234567890abcdef12345678"
        
        # 设置环境变量
        self.env_patcher = patch.dict(os.environ, {
            'ETHERSCAN_API_KEY': 'test_api_key',
            'ETHEREUM_RPC_URL': 'https://test.rpc.url'
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """集成测试清理"""
        self.env_patcher.stop()
    
    @patch('historical_token_balance_checker.Web3')
    @patch('historical_token_balance_checker.BlockTimeConverter')
    def test_full_workflow_single_address(self, mock_block_converter, mock_web3):
        """测试完整的单地址查询工作流程"""
        # 完整的模拟设置
        mock_web3_instance = Mock()
        mock_web3_instance.eth.call.return_value.hex.return_value = '0x000000000000000000000000000000000000000000000000000000e8d4a51000'
        mock_web3.return_value = mock_web3_instance
        mock_web3.to_checksum_address.return_value = self.test_address
        
        mock_converter_instance = Mock()
        mock_converter_instance.get_block_number_by_timestamp.return_value = 18000000
        mock_converter_instance.get_block_by_timestamp.return_value = 18000000
        mock_converter_instance.datetime_to_timestamp.return_value = 1704110400  # 2024-01-01 12:00:00 UTC
        mock_block_converter.return_value = mock_converter_instance
        
        with patch('os.makedirs'), \
             patch('builtins.open', create=True) as mock_open:
            
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # 创建并运行检查器
            checker = HistoricalTokenBalanceChecker(
                target_time=self.target_time,
                token=self.token,
                network=self.network,
                address_to_check=self.test_address
            )
            
            result = checker.run(mode='single')
            
            # 验证完整工作流程
            self.assertIsInstance(result, dict)
            self.assertEqual(result['address'], self.test_address)
            self.assertEqual(result['token'], self.token.upper())
            self.assertEqual(result['network'], self.network.lower())
            self.assertIn('balance_tokens', result)
            self.assertIn('block_number', result)
            
            # 验证文件保存被调用
            mock_open.assert_called()


if __name__ == '__main__':
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加单元测试
    test_suite.addTest(unittest.makeSuite(TestHistoricalTokenBalanceChecker))
    test_suite.addTest(unittest.makeSuite(TestHistoricalTokenBalanceCheckerIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 打印测试结果摘要
    print(f"\n{'='*60}")
    print(f"测试摘要:")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    print(f"跳过数: {len(result.skipped)}")
    print(f"成功率: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*60}")
