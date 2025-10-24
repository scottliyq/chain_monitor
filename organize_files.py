#!/usr/bin/env python3
"""
文件整理脚本
将所有结果文件移动到 temp 目录
"""

import os
import shutil
import glob
from pathlib import Path

def move_result_files_to_temp():
    """将结果文件移动到 temp 目录"""
    
    # 确保 temp 目录存在
    temp_dir = Path('temp')
    temp_dir.mkdir(exist_ok=True)
    
    # 定义需要移动的文件模式
    file_patterns = [
        'usdt_large_transfers_*.json',
        'usdt_balance_surge_*.json',
        'address_interactions_*.json',
        'concrete_stable_*.json',
        'concrete_stable_*.txt',
        '*.log'
    ]
    
    moved_files = []
    
    print("🔄 开始整理结果文件到 temp 目录...")
    
    for pattern in file_patterns:
        # 查找匹配的文件
        matching_files = glob.glob(pattern)
        
        for file_path in matching_files:
            file_name = os.path.basename(file_path)
            dest_path = temp_dir / file_name
            
            try:
                # 如果目标文件已存在，添加时间戳后缀
                if dest_path.exists():
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%H%M%S')
                    name_parts = file_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_name = f"{name_parts[0]}_moved_{timestamp}.{name_parts[1]}"
                    else:
                        new_name = f"{file_name}_moved_{timestamp}"
                    dest_path = temp_dir / new_name
                
                # 移动文件
                shutil.move(file_path, dest_path)
                moved_files.append((file_path, dest_path))
                print(f"✅ 已移动: {file_path} -> {dest_path}")
                
            except Exception as e:
                print(f"❌ 移动文件 {file_path} 时出错: {e}")
    
    if moved_files:
        print(f"\n🎉 成功移动了 {len(moved_files)} 个文件到 temp 目录")
    else:
        print("\n✅ 没有发现需要移动的结果文件")
    
    # 显示 temp 目录内容
    temp_files = list(temp_dir.glob('*'))
    if temp_files:
        print(f"\n📁 temp 目录当前包含 {len(temp_files)} 个文件:")
        for file_path in sorted(temp_files):
            size = file_path.stat().st_size
            print(f"   📄 {file_path.name} ({size:,} bytes)")

def main():
    """主函数"""
    print("🚀 结果文件整理工具")
    print("=" * 50)
    
    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    move_result_files_to_temp()
    
    print("\n💡 提示:")
    print("   所有新生成的结果文件现在都会自动保存到 temp 目录")
    print("   可以定期清理 temp 目录来节省磁盘空间")

if __name__ == "__main__":
    main()