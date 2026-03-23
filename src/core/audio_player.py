#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台音频播放模块
支持macOS、Linux和Windows
"""

import os
import sys
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)


class SystemAudioPlayer:
    """系统音频播放器，自动选择合适的播放方法"""
    
    def __init__(self):
        self.system = platform.system()
        self.preferred_method = self._detect_player()
    
    def _detect_player(self):
        """检测系统可用的音频播放器"""
        if self.system == "Darwin":  # macOS
            return "afplay"
        elif self.system == "Linux":
            # 尝试检测Linux上可用的播放器
            for player in ["mpg123", "ffplay", "aplay", "play"]:
                try:
                    subprocess.run([player, "--version"], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 timeout=1)
                    return player
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            return None
        elif self.system == "Windows":
            return "windows"
        else:
            return None
    
    def play(self, audio_file, loop=False, volume=1.0):
        """
        播放音频文件
        
        Args:
            audio_file: 音频文件路径
            loop: 是否循环播放（仅部分播放器支持）
            volume: 音量（0.0-1.0）
            
        Returns:
            bool: 播放是否成功启动
        """
        if not os.path.exists(audio_file):
            logger.error(f"音频文件不存在: {audio_file}")
            return False
        
        try:
            if self.preferred_method == "afplay":
                # macOS的afplay命令
                cmd = ["afplay"]
                if volume < 1.0:
                    cmd.extend(["-v", str(volume)])
                cmd.append(audio_file)
                
                # 非阻塞方式播放
                subprocess.Popen(cmd, 
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                return True
                
            elif self.preferred_method == "mpg123":
                # Linux的mpg123
                cmd = ["mpg123", "-q"]  # -q 静默模式
                if loop:
                    cmd.append("--loop")
                    cmd.append("-1")
                cmd.append(audio_file)
                
                subprocess.Popen(cmd,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                return True
                
            elif self.preferred_method == "windows":
                # Windows使用winsound
                import winsound
                winsound.PlaySound(audio_file, 
                                 winsound.SND_FILENAME | winsound.SND_ASYNC)
                return True
            else:
                logger.error(f"不支持的系统或未找到音频播放器: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
            return False
    
    def stop(self):
        """停止播放（有限支持）"""
        try:
            if self.system == "Darwin":
                # macOS上终止afplay进程
                subprocess.run(["killall", "afplay"],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            elif self.system == "Linux":
                # Linux上终止音频播放器进程
                for player in ["mpg123", "ffplay", "aplay", "play"]:
                    subprocess.run(["killall", player],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.warning(f"停止播放时出错: {e}")


def play_alert_sound(alert_file=None):
    """
    播放提示音的便捷函数
    
    Args:
        alert_file: 音频文件路径，默认使用resource/alert.mp3
        
    Returns:
        bool: 是否成功播放
    """
    if alert_file is None:
        # 默认使用resource/alert.mp3
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alert_file = os.path.join(script_dir, "resource", "alert.mp3")
    
    if not os.path.exists(alert_file):
        logger.warning(f"提示音文件不存在: {alert_file}")
        return False
    
    player = SystemAudioPlayer()
    
    if player.preferred_method:
        logger.info(f"🔔 播放提示音: {os.path.basename(alert_file)}")
        return player.play(alert_file, loop=False, volume=0.8)
    else:
        logger.warning("未找到可用的音频播放器")
        return False
