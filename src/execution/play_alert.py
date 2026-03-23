#!/usr/bin/env python3
"""
播放 alert.mp3 文件
"""

import sys
import os
from pathlib import Path

try:
    from core.audio_player import SystemAudioPlayer
except ImportError:
    print("❌ 无法导入 audio_player")
    sys.exit(1)

def play_alert():
    """播放 alert.mp3 文件"""
    
    # alert.mp3 文件路径
    alert_file = "/Users/scottliyq/go/hardhat_space/chain_monitor/alert.mp3"
    
    # 检查文件是否存在
    if not os.path.exists(alert_file):
        print(f"❌ 文件不存在: {alert_file}")
        return False
    
    # 创建播放器
    player = SystemAudioPlayer()
    
    # 显示文件信息
    file_size = os.path.getsize(alert_file)
    print(f"🎵 准备播放 alert.mp3")
    print(f"📁 文件路径: {alert_file}")
    print(f"📊 文件大小: {file_size:,} 字节")
    print(f"🔧 播放方法: {player.preferred_method}")
    print("=" * 50)
    
    try:
        # 播放文件
        print("🎵 开始播放 alert.mp3...")
        success = player.play(alert_file, loop=False, volume=0.7)
        
        if success:
            print("✅ 播放成功!")
            print("按 Enter 键停止播放...")
            input()
            player.stop()
            print("🔇 播放已停止")
        else:
            print("❌ 播放失败")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断播放")
        player.stop()
        return False
    except Exception as e:
        print(f"❌ 播放过程中出错: {e}")
        player.stop()
        return False

if __name__ == "__main__":
    play_alert()
