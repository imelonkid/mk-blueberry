#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import subprocess
import argparse
import shutil
from pathlib import Path

# 导入PDF后处理模块
from pdf_post_process import remove_slash_marks

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("pdf_translator_bridge")

# 结果文件夹
RESULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(RESULT_FOLDER, exist_ok=True)

def translate_document(pdf_path, task_id=None, source_lang='en', target_lang='zh', provider='deepseek', model='deepseek-chat', format='dual', post_process=True, force=False):
    """
    翻译PDF文档
    
    参数:
        pdf_path (str): PDF文件路径
        task_id (str): 任务ID，用于生成结果文件名
        source_lang (str): 源语言
        target_lang (str): 目标语言
        provider (str): 翻译提供商 ('deepseek'/'gpt'/'anthropic'/'azure'等)
        model (str): 模型名称
        format (str): 输出格式, 'dual'表示中英对照, 'mono'表示仅中文
        post_process (bool): 是否进行后处理去除斜杠标记
        force (bool): 是否强制重新翻译，即使已有翻译结果
        
    返回:
        str: 翻译后的PDF文件路径，如果失败则返回None
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF文件不存在: {pdf_path}")
        return None
    
    if not task_id:
        logger.warning("未提供任务ID，将使用PDF文件名")
        task_id = os.path.basename(pdf_path).split('.')[0]
    
    logger.info(f"开始翻译文档: {pdf_path}")
    logger.info(f"任务ID: {task_id}")
    logger.info(f"源语言: {source_lang}, 目标语言: {target_lang}")
    logger.info(f"提供商: {provider}, 模型: {model}")
    logger.info(f"输出格式: {format}")
    logger.info(f"强制重新翻译: {force}")
    
    # 结果文件路径
    result_folder = os.path.join(RESULT_FOLDER, task_id)
    os.makedirs(result_folder, exist_ok=True)
    
    # 根据格式确定最终的文件名
    if format == 'mono':
        result_filename = f"{task_id}_translated_mono.pdf"  # 仅中文版
        expected_generated_filename = f"{os.path.basename(pdf_path).rsplit('.', 1)[0]}-mono.pdf"
    else:  # dual or default
        result_filename = f"{task_id}_translated_dual.pdf"  # 中英对照版
        expected_generated_filename = f"{os.path.basename(pdf_path).rsplit('.', 1)[0]}-dual.pdf"
        
    result_path = os.path.join(result_folder, result_filename)
    
    # 如果不是强制重新翻译，检查是否已有翻译结果
    if not force and os.path.exists(result_path):
        logger.info(f"已找到现有翻译结果: {result_path}，直接返回")
        return result_path
    
    try:
        # 构建pdf2zh命令 - 根据pdf2zh的帮助信息调整参数格式
        # 尝试多种方式找到pdf2zh命令
        pdf2zh_cmd_paths = [
            os.environ.get('PDF2ZH_PATH', ''),  # 从环境变量获取（由start.sh设置）
            "pdf2zh",  # 系统路径
            os.path.expanduser("~/.local/bin/pdf2zh"),  # 用户安装路径
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "venv/bin/pdf2zh"),  # 虚拟环境路径
            "/usr/local/bin/pdf2zh",  # 全局安装路径
            "/root/.local/bin/pdf2zh",  # root用户安装路径
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/pdf2zh")  # 当前目录bin文件夹
        ]
        
        # 过滤掉空路径
        pdf2zh_cmd_paths = [path for path in pdf2zh_cmd_paths if path]
        
        # 检查是否存在环境变量设置的路径
        if os.environ.get('PDF2ZH_PATH'):
            logger.info(f"从环境变量获取pdf2zh路径: {os.environ.get('PDF2ZH_PATH')}")
        
        # 系统信息记录，用于排查不同系统上的问题
        try:
            import platform
            system_info = {
                "系统": platform.system(),
                "发行版": platform.release(),
                "版本": platform.version(),
                "架构": platform.machine(),
                "Python版本": platform.python_version()
            }
            logger.info(f"系统信息: {json.dumps(system_info, ensure_ascii=False)}")
        except Exception as e:
            logger.warning(f"获取系统信息时出错: {str(e)}")
        
        # 检查哪个pdf2zh路径存在并可执行
        pdf2zh_path = None
        for cmd_path in pdf2zh_cmd_paths:
            logger.info(f"检查pdf2zh路径: {cmd_path}")
            if os.path.exists(cmd_path):
                if os.access(cmd_path, os.X_OK):
                    pdf2zh_path = cmd_path
                    logger.info(f"找到可执行的pdf2zh命令: {pdf2zh_path}")
                    break
                else:
                    logger.warning(f"文件存在但不可执行: {cmd_path}")
            elif " " not in cmd_path and shutil.which(cmd_path):  # 检查系统路径中的命令
                pdf2zh_path = shutil.which(cmd_path)
                logger.info(f"从系统路径找到pdf2zh命令: {pdf2zh_path}")
                break
        
        # 如果没有找到pdf2zh，尝试安装
        if not pdf2zh_path:
            logger.warning("未找到pdf2zh命令，尝试检查Python环境...")
            try:
                # 检查当前Python路径
                python_path = sys.executable
                logger.info(f"当前Python路径: {python_path}")
                
                # 检查pip是否可用
                logger.info("检查pip是否可用...")
                pip_check = subprocess.run(
                    [python_path, "-m", "pip", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if pip_check.returncode == 0:
                    logger.info(f"pip可用: {pip_check.stdout.strip()}")
                    
                    # 检查pdf2zh包是否已安装
                    logger.info("检查pdf2zh包是否已安装...")
                    pip_list = subprocess.run(
                        [python_path, "-m", "pip", "list"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    logger.debug(f"pip list输出: {pip_list.stdout}")
                    
                    if "paper2translate" in pip_list.stdout or "pdf2zh" in pip_list.stdout:
                        logger.info("pdf2zh包已安装，但命令不可用，可能是PATH问题")
                        
                        # 尝试找到安装的包路径
                        try:
                            import site
                            user_site = site.getusersitepackages()
                            logger.info(f"用户site-packages路径: {user_site}")
                            
                            # 检查可能的bin目录
                            bin_paths = [
                                os.path.join(os.path.dirname(user_site), "bin"),
                                os.path.join(os.path.dirname(os.path.dirname(user_site)), "bin")
                            ]
                            
                            for bin_path in bin_paths:
                                if os.path.exists(bin_path):
                                    logger.info(f"检查bin目录: {bin_path}")
                                    if os.path.exists(os.path.join(bin_path, "pdf2zh")):
                                        pdf2zh_path = os.path.join(bin_path, "pdf2zh")
                                        logger.info(f"在bin目录找到pdf2zh: {pdf2zh_path}")
                                        break
                        except Exception as e:
                            logger.exception(f"查找site-packages时出错: {str(e)}")
                    else:
                        logger.warning("pdf2zh包未安装，尝试安装...")
                        # 尝试安装pdf2zh
                        install_result = subprocess.run(
                            [python_path, "-m", "pip", "install", "--user", "-e", "git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        logger.info(f"安装输出: {install_result.stdout}")
                        if install_result.stderr:
                            logger.warning(f"安装警告/错误: {install_result.stderr}")
                            
                        if install_result.returncode == 0:
                            logger.info("pdf2zh安装成功")
                            # 重新检查命令
                            pdf2zh_path = shutil.which("pdf2zh")
                            if pdf2zh_path:
                                logger.info(f"安装后找到pdf2zh命令: {pdf2zh_path}")
                            else:
                                logger.warning("安装成功，但仍然找不到pdf2zh命令")
                                
                                # 尝试在.local/bin中查找
                                local_bin_path = os.path.expanduser("~/.local/bin/pdf2zh")
                                if os.path.exists(local_bin_path):
                                    pdf2zh_path = local_bin_path
                                    logger.info(f"在.local/bin中找到pdf2zh: {pdf2zh_path}")
                        else:
                            logger.error(f"pdf2zh安装失败: {install_result.stderr}")
                else:
                    logger.error(f"pip不可用: {pip_check.stderr}")
            except Exception as e:
                logger.exception(f"检查和安装pdf2zh时出错: {str(e)}")
            
            # 如果仍然找不到，检查几种常见的实现方式
            if not pdf2zh_path:
                logger.warning("尝试在Python路径中搜索pdf2zh模块...")
                try:
                    # 检查site-packages中可能的入口点脚本
                    result = subprocess.run(
                        [python_path, "-c", "import importlib.util; import site; import os; print(','.join([p for p in site.getsitepackages()])+ ',' + site.getusersitepackages())"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        site_packages = result.stdout.strip().split(',')
                        for site_pkg in site_packages:
                            logger.info(f"检查site-package路径: {site_pkg}")
                            # 检查是否有paper2translate或pdf2zh包
                            for pkg_name in ['paper2translate', 'pdf2zh']:
                                pkg_path = os.path.join(site_pkg, pkg_name)
                                if os.path.exists(pkg_path):
                                    logger.info(f"找到包目录: {pkg_path}")
                                    # 可能的入口点脚本
                                    script_paths = [
                                        os.path.join(pkg_path, "cli.py"),
                                        os.path.join(pkg_path, "main.py"),
                                        os.path.join(pkg_path, "__main__.py"),
                                        os.path.join(pkg_path, "pdf2zh.py")
                                    ]
                                    for script in script_paths:
                                        if os.path.exists(script):
                                            logger.info(f"找到可能的入口点脚本: {script}")
                                            # 如果找到脚本，可以直接用Python执行它
                                            pdf2zh_path = f"{python_path} {script}"
                                            logger.info(f"将使用Python直接执行脚本: {pdf2zh_path}")
                                            break
                except Exception as e:
                    logger.exception(f"搜索pdf2zh模块时出错: {str(e)}")
                
            # 如果仍然找不到，使用默认命令并记录警告
            if not pdf2zh_path:
                logger.warning("无法找到或安装pdf2zh命令，将使用默认'pdf2zh'命令，可能会失败")
                pdf2zh_path = "pdf2zh"
        
        # 设置环境变量
        env = os.environ.copy()
        # 检查关键环境变量
        if 'PYTHONPATH' not in env:
            logger.warning("PYTHONPATH环境变量未设置")
        if 'PATH' in env:
            logger.info(f"PATH环境变量: {env['PATH']}")
        else:
            logger.warning("PATH环境变量未设置")
        if 'OPENAI_API_KEY' not in env and 'DEEPSEEK_API_KEY' not in env:
            logger.warning("未找到OPENAI_API_KEY或DEEPSEEK_API_KEY环境变量")
            
        # 检查Python可执行文件是否在PATH中
        python_dirs = []
        if sys.executable:
            python_dir = os.path.dirname(sys.executable)
            if python_dir not in env.get('PATH', ''):
                logger.warning(f"Python目录不在PATH中: {python_dir}")
                # 添加到PATH
                if 'PATH' in env:
                    env['PATH'] = f"{python_dir}:{env['PATH']}"
                else:
                    env['PATH'] = python_dir
                logger.info(f"已将Python目录添加到PATH: {env['PATH']}")
                python_dirs.append(python_dir)
                
        # 构建命令
        # 判断pdf2zh_path是否包含python调用，如果是，则需要特殊处理
        if pdf2zh_path.startswith(sys.executable) or " " in pdf2zh_path:
            logger.info(f"使用Python直接执行脚本: {pdf2zh_path}")
            parts = pdf2zh_path.split()
            if len(parts) >= 2:  # 例如: "/usr/bin/python3 /path/to/script.py"
                pdf2zh_cmd = [
                    parts[0],  # Python解释器
                    parts[1],  # 脚本路径
                    pdf_path,  # 文件路径作为位置参数
                    "--lang-in", source_lang,
                    "--lang-out", target_lang,
                    "--service", f"{provider}:{model}" if model else provider,
                    "--output", result_folder,  # 指定输出目录而不是文件
                    "--thread", "2",
                    "--debug"  # 添加调试标志
                ]
            else:
                logger.error(f"无效的Python脚本路径: {pdf2zh_path}")
                pdf2zh_cmd = []
        else:
            pdf2zh_cmd = [
                pdf2zh_path,
                pdf_path,  # 文件路径作为位置参数
                "--lang-in", source_lang,
                "--lang-out", target_lang,
                "--service", f"{provider}:{model}" if model else provider,
                "--output", result_folder,  # 指定输出目录而不是文件
                "--thread", "2",
                "--debug"  # 添加调试标志
            ]
        
        logger.info(f"完整命令行: {' '.join(pdf2zh_cmd)}")
        logger.info(f"开始执行pdf2zh命令，工作目录: {os.getcwd()}")
        logger.info(f"结果目录: {result_folder}")
        
        # 执行pdf2zh命令，设置超时
        try:
            process = subprocess.run(
                pdf2zh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,  # 设为False，我们自己处理错误
                env=env,  # 传递当前环境变量，包括API密钥
                timeout=300  # 设置5分钟超时
            )
            
            # 记录命令输出
            if process.stdout:
                logger.info(f"命令标准输出:\n{process.stdout}")
            if process.stderr:
                if process.returncode != 0:
                    logger.error(f"命令错误输出:\n{process.stderr}")
                else:
                    logger.warning(f"命令警告输出:\n{process.stderr}")
                    
        except subprocess.TimeoutExpired:
            logger.error("pdf2zh执行超时（5分钟）")
            return None
        except FileNotFoundError as e:
            logger.error(f"翻译过程中发生错误: {str(e)}")
            logger.error(f"无法找到pdf2zh命令。请确保已正确安装pdf2zh工具。")
            logger.error(f"PATH环境变量: {env.get('PATH', '未设置')}")
            logger.error(f"尝试执行: pip install -e git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate")
            return None
        except Exception as e:
            logger.error(f"执行pdf2zh命令时发生错误: {str(e)}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return None
        
        # 检查返回码
        if process.returncode != 0:
            logger.error(f"pdf2zh执行失败 (返回码 {process.returncode})")
            logger.error(f"错误信息: {process.stderr}")
            return None
        
        logger.info(f"pdf2zh执行成功")
        
        # 验证结果文件是否存在
        if os.path.exists(result_path):
            logger.info(f"翻译完成，文件保存在: {result_path}")
            
            # 后处理：去除斜杠标记
            if post_process and format == 'mono':
                try:
                    logger.info(f"开始对文件进行后处理以去除斜杠标记: {result_path}")
                    post_processed_path = os.path.join(result_folder, f"{task_id}_processed.pdf")
                    if remove_slash_marks(result_path, post_processed_path):
                        logger.info(f"后处理成功，更新结果文件: {post_processed_path}")
                        # 备份原始翻译文件
                        original_backup = os.path.join(result_folder, f"{task_id}_original.pdf")
                        shutil.copy2(result_path, original_backup)
                        # 用后处理结果替换原始结果
                        shutil.move(post_processed_path, result_path)
                    else:
                        logger.warning(f"后处理失败，将使用原始翻译结果")
                except Exception as e:
                    logger.exception(f"后处理过程中发生错误: {str(e)}")
            
            return result_path
        else:
            # 检查输出目录下是否有生成的PDF
            base_name = os.path.basename(pdf_path).rsplit('.', 1)[0]
            logger.info(f"结果文件不存在于预期位置，检查其他可能的文件名")
            logger.info(f"基础文件名: {base_name}")
            
            # 列出结果目录中的所有文件
            try:
                if os.path.exists(result_folder):
                    all_files = os.listdir(result_folder)
                    logger.info(f"结果目录中的所有文件: {all_files}")
                else:
                    logger.error(f"结果目录不存在: {result_folder}")
                    all_files = []
            except Exception as e:
                logger.exception(f"列出结果目录文件时出错: {str(e)}")
                all_files = []
            
            # 首先检查预期的特定格式文件名
            expected_file_path = os.path.join(result_folder, expected_generated_filename)
            logger.info(f"检查预期的特定格式文件: {expected_file_path}")
            if os.path.exists(expected_file_path):
                # 找到对应格式的文件，移动到标准位置
                logger.info(f"找到预期的特定格式文件: {expected_file_path}")
                shutil.move(expected_file_path, result_path)
                logger.info(f"已移动到标准位置: {result_path}")
                return result_path
            
            # 然后检查其他可能的文件名
            potential_files = [
                f"{task_id}_translated.pdf",
                f"{task_id}_{base_name}_translated.pdf",
                f"{task_id}_{base_name}-translated.pdf",
                f"{base_name}-dual.pdf",
                f"{base_name}-mono.pdf"
            ]
            
            logger.info(f"检查其他可能的文件名: {potential_files}")
            
            # 检查指定的结果目录
            for filename in potential_files:
                pdf_path = os.path.join(result_folder, filename)
                logger.info(f"检查可能的文件: {pdf_path}")
                if os.path.exists(pdf_path):
                    # 找到文件，移动到标准位置
                    if pdf_path != result_path:
                        logger.info(f"找到文件，移动到标准位置: {pdf_path} -> {result_path}")
                        shutil.move(pdf_path, result_path)
                    else:
                        logger.info(f"找到生成的文件: {pdf_path}")
                    
                    # 后处理：去除斜杠标记
                    if post_process and format == 'mono':
                        try:
                            logger.info(f"开始对文件进行后处理以去除斜杠标记: {result_path}")
                            post_processed_path = os.path.join(result_folder, f"{task_id}_processed.pdf")
                            if remove_slash_marks(result_path, post_processed_path):
                                logger.info(f"后处理成功，更新结果文件: {post_processed_path}")
                                # 备份原始翻译文件
                                original_backup = os.path.join(result_folder, f"{task_id}_original.pdf")
                                shutil.copy2(result_path, original_backup)
                                # 用后处理结果替换原始结果
                                shutil.move(post_processed_path, result_path)
                            else:
                                logger.warning(f"后处理失败，将使用原始翻译结果")
                        except Exception as e:
                            logger.exception(f"后处理过程中发生错误: {str(e)}")
                    
                    return result_path
            
            # 然后检查当前工作目录
            logger.info(f"检查当前工作目录: {os.getcwd()}")
            try:
                curr_dir_files = os.listdir(os.getcwd())
                logger.info(f"当前工作目录中的文件: {curr_dir_files}")
            except Exception as e:
                logger.exception(f"列出当前工作目录文件时出错: {str(e)}")
            
            for filename in potential_files:
                curr_dir_path = os.path.join(os.getcwd(), filename)
                logger.info(f"检查当前工作目录中的文件: {curr_dir_path}")
                if os.path.exists(curr_dir_path):
                    # 移动文件到结果目录
                    logger.info(f"在当前目录找到生成的文件，移动到结果目录: {curr_dir_path} -> {result_path}")
                    shutil.move(curr_dir_path, result_path)
                    
                    # 后处理：去除斜杠标记
                    if post_process and format == 'mono':
                        try:
                            logger.info(f"开始对文件进行后处理以去除斜杠标记: {result_path}")
                            post_processed_path = os.path.join(result_folder, f"{task_id}_processed.pdf")
                            if remove_slash_marks(result_path, post_processed_path):
                                logger.info(f"后处理成功，更新结果文件: {post_processed_path}")
                                # 备份原始翻译文件
                                original_backup = os.path.join(result_folder, f"{task_id}_original.pdf")
                                shutil.copy2(result_path, original_backup)
                                # 用后处理结果替换原始结果
                                shutil.move(post_processed_path, result_path)
                            else:
                                logger.warning(f"后处理失败，将使用原始翻译结果")
                        except Exception as e:
                            logger.exception(f"后处理过程中发生错误: {str(e)}")
                    
                    return result_path
            
            # 检查其他可能位置
            logger.warning("在常规位置未找到生成的文件，检查父目录和pdf2zh可能生成的其他位置")
            try:
                parent_dir = os.path.dirname(result_folder)
                if os.path.exists(parent_dir):
                    parent_files = os.listdir(parent_dir)
                    logger.info(f"父目录中的文件: {parent_files}")
                    # 查找任何以base_name开头并以.pdf结尾的文件
                    for filename in parent_files:
                        if filename.startswith(base_name) and filename.endswith(".pdf") and "translated" in filename:
                            parent_pdf_path = os.path.join(parent_dir, filename)
                            logger.info(f"在父目录找到可能的翻译文件: {parent_pdf_path}")
                            shutil.copy2(parent_pdf_path, result_path)
                            logger.info(f"已复制到结果路径: {result_path}")
                            return result_path
            except Exception as e:
                logger.exception(f"检查父目录时出错: {str(e)}")
            
            # 全面搜索整个项目目录
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                logger.info(f"在项目根目录搜索翻译后的PDF: {project_root}")
                for root, dirs, files in os.walk(project_root):
                    for filename in files:
                        if filename.startswith(base_name) and filename.endswith(".pdf") and ("translated" in filename or "-dual" in filename or "-mono" in filename):
                            found_path = os.path.join(root, filename)
                            logger.info(f"在项目目录找到可能的翻译文件: {found_path}")
                            
                            # 如果文件是新创建的（1小时内），很可能是我们要找的
                            file_created_time = os.path.getctime(found_path)
                            if time.time() - file_created_time < 3600:  # 1小时 = 3600秒
                                logger.info(f"文件创建于 {time.ctime(file_created_time)}，复制到结果路径")
                                shutil.copy2(found_path, result_path)
                                logger.info(f"已复制到结果路径: {result_path}")
                                return result_path
            except Exception as e:
                logger.exception(f"全面搜索项目目录时出错: {str(e)}")
            
            logger.error(f"pdf2zh成功执行，但结果文件不存在: {result_path}")
            logger.error(f"已检查以下路径:")
            logger.error(f"1. 预期的结果路径: {result_path}")
            logger.error(f"2. 预期的特定格式文件: {expected_file_path}")
            logger.error(f"3. 结果目录中其他可能的文件名: {[os.path.join(result_folder, f) for f in potential_files]}")
            logger.error(f"4. 当前工作目录: {[os.path.join(os.getcwd(), f) for f in potential_files]}")
            return None
            
    except Exception as e:
        logger.exception(f"翻译过程中发生错误: {str(e)}")
        return None

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PDF翻译桥接服务')
    parser.add_argument('--port', type=int, default=5000, help='服务端口号')
    parser.add_argument('pdf_file', nargs='?', help='要翻译的PDF文件路径')
    
    args = parser.parse_args()
    
    if args.pdf_file:
        # 如果提供了PDF文件，直接翻译它
        result = translate_document(args.pdf_file)
        if result:
            print(f"翻译完成，结果保存在: {result}")
            return 0
        else:
            print("翻译失败")
            return 1
    else:
        # 导入Flask并启动服务
        try:
            from flask import Flask, request, jsonify, send_from_directory
            from flask_cors import CORS
            from werkzeug.utils import secure_filename
            import uuid
            
            # 项目根目录，用于服务静态文件
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 上传目录
            UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # 保存任务状态
            tasks = {}
            
            app = Flask(__name__, static_folder=project_root, static_url_path='')
            CORS(app)
            
            # 允许上传的文件类型
            ALLOWED_EXTENSIONS = {'pdf'}
            
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
            
            @app.route('/')
            def index():
                return app.send_static_file('index.html')
                
            @app.route('/translate.html')
            def translate_page():
                return app.send_static_file('translate.html')
            
            @app.route('/api/health')
            def health():
                return jsonify({"message": "PDF翻译服务后端", "status": "运行中"})
            
            @app.route('/api/upload', methods=['POST'])
            def upload_file():
                # 检查是否有文件
                if 'file' not in request.files:
                    return jsonify({"error": "没有文件"}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({"error": "未选择文件"}), 400
                
                if file and allowed_file(file.filename):
                    # 生成唯一的任务ID
                    task_id = str(uuid.uuid4())
                    
                    # 安全地获取文件名
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
                    
                    # 保存文件
                    file.save(file_path)
                    
                    # 初始化任务状态
                    tasks[task_id] = {
                        "id": task_id,
                        "filename": filename,
                        "original_path": file_path,
                        "result_path": None,
                        "status": "pending",
                        "message": "任务已创建"
                    }
                    
                    logger.info(f"文件已上传: {file_path}, 任务ID: {task_id}")
                    
                    return jsonify({
                        "task_id": task_id,
                        "status": "pending",
                        "message": "文件上传成功，等待处理"
                    })
                
                return jsonify({"error": "不支持的文件类型"}), 400
            
            @app.route('/api/translate_document', methods=['POST'])
            def api_translate_document():
                logger.info("接收到/api/translate_document请求")
                
                # 记录请求内容
                try:
                    if request.is_json:
                        req_data = request.get_json()
                        logger.info(f"请求JSON数据: {json.dumps(req_data, ensure_ascii=False)}")
                    elif request.form:
                        logger.info(f"请求表单数据: {dict(request.form)}")
                    elif request.data:
                        logger.info(f"请求原始数据: {request.data.decode('utf-8', errors='replace')[:1000]}")
                    else:
                        logger.warning("未发现请求数据")
                        
                    # 记录请求头信息
                    headers = dict(request.headers)
                    logger.info(f"请求头信息: {json.dumps(headers, ensure_ascii=False)}")
                except Exception as e:
                    logger.exception(f"记录请求数据时出错: {str(e)}")
                
                # 调用原有处理函数
                return api_translate()
            
            @app.route('/api/translate', methods=['POST'])
            def api_translate():
                logger.info("接收到/api/translate请求")
                
                # 记录原始请求内容
                try:
                    if request.is_json:
                        req_data = request.get_json() 
                        logger.info(f"请求JSON数据: {json.dumps(req_data, ensure_ascii=False)}")
                    elif request.form:
                        logger.info(f"请求表单数据: {dict(request.form)}")
                    elif request.data:
                        logger.info(f"请求原始数据: {request.data.decode('utf-8', errors='replace')[:1000]}")
                    else:
                        logger.warning("未发现请求数据")
                except Exception as e:
                    logger.exception(f"记录请求数据时出错: {str(e)}")
                
                try:
                    # 尝试解析JSON数据
                    data = request.get_json()
                    if not data:
                        logger.error("请求中没有JSON数据")
                        return jsonify({"error": "无效的请求数据，未提供JSON"}), 400
                except Exception as e:
                    logger.exception(f"解析JSON数据失败: {str(e)}")
                    return jsonify({"error": f"解析请求数据失败: {str(e)}"}), 400
                
                task_id = data.get('task_id')
                if not task_id:
                    logger.error("请求中缺少task_id字段")
                    return jsonify({"error": "无效的请求数据，缺少task_id"}), 400
                
                source_lang = data.get('source_lang', 'en')
                target_lang = data.get('target_lang', 'zh')
                provider = data.get('provider', 'deepseek')
                model = data.get('model', 'deepseek-chat')
                output_format = data.get('format', 'dual')  # 新增格式参数
                post_process = data.get('post_process', True)  # 新增后处理参数
                force = data.get('force', False)  # 新增强制重新翻译参数
                
                logger.info(f"翻译参数 - task_id: {task_id}, 源语言: {source_lang}, 目标语言: {target_lang}, "
                           f"提供商: {provider}, 模型: {model}, 格式: {output_format}, "
                           f"后处理: {post_process}, 强制重新翻译: {force}")
                
                if output_format not in ['mono', 'dual']:
                    logger.warning(f"不支持的输出格式: {output_format}，使用默认格式: dual")
                    output_format = 'dual'  # 默认使用中英对照格式
                
                if task_id not in tasks:
                    logger.error(f"无效的任务ID: {task_id}")
                    # 列出现有任务ID以便调试
                    available_tasks = list(tasks.keys())
                    logger.info(f"可用的任务ID: {available_tasks}")
                    return jsonify({"error": "无效的任务ID"}), 400
                
                task = tasks[task_id]
                logger.info(f"找到任务: {task}")
                
                if task['status'] not in ['pending', 'failed'] and not force:
                    # 如果任务已经完成，并且不是强制重新翻译，则直接返回现有结果
                    if task['status'] == 'completed':
                        logger.info(f"任务已完成，直接返回结果: {task_id}")
                        return jsonify({
                            "task_id": task_id,
                            "status": task['status'],
                            "message": "翻译已完成",
                            "reused": True
                        })
                    logger.warning(f"任务状态为 {task['status']}，无法开始翻译")
                    return jsonify({"error": f"任务状态为 {task['status']}，无法开始翻译"}), 400
                
                # 更新任务状态
                task['status'] = 'processing'
                task['message'] = "翻译处理中..."
                
                logger.info(f"开始翻译任务 {task_id}, 源语言: {source_lang}, 目标语言: {target_lang}, 提供商: {provider}, 格式: {output_format}, 后处理: {post_process}, 强制重新翻译: {force}")
                logger.info(f"原始文件路径: {task['original_path']}")
                
                try:
                    # 确认原始文件存在
                    if not os.path.exists(task['original_path']):
                        logger.error(f"原始文件不存在: {task['original_path']}")
                        task['status'] = 'failed'
                        task['message'] = f"原始文件不存在: {os.path.basename(task['original_path'])}"
                        return jsonify({"error": "原始文件不存在"}), 404
                    
                    # 调用翻译函数
                    result_path = translate_document(
                        task['original_path'],
                        task_id=task_id,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        provider=provider,
                        model=model,
                        format=output_format,
                        post_process=post_process,
                        force=force
                    )
                    
                    if result_path:
                        task['result_path'] = result_path
                        task['status'] = 'completed'
                        task['message'] = "翻译完成"
                        logger.info(f"任务 {task_id} 翻译完成: {result_path}")
                    else:
                        task['status'] = 'failed'
                        task['message'] = "翻译失败"
                        logger.error(f"任务 {task_id} 翻译失败，result_path为空")
                    
                    return jsonify({
                        "task_id": task_id,
                        "status": task['status'],
                        "message": task['message']
                    })
                except Exception as e:
                    logger.exception(f"启动翻译任务 {task_id} 时出错: {str(e)}")
                    task['status'] = 'failed'
                    task['message'] = f"启动翻译失败: {str(e)}"
                    return jsonify({"error": str(e)}), 500
            
            @app.route('/api/files/<task_id>', methods=['GET'])
            def get_original_file(task_id):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                if not os.path.exists(task['original_path']):
                    return jsonify({"error": "原始文件不存在"}), 404
                
                return send_from_directory(
                    os.path.dirname(task['original_path']), 
                    os.path.basename(task['original_path']), 
                    as_attachment=False
                )
            
            @app.route('/api/translated_files/<task_id>/<filename>', methods=['GET'])
            def get_translated_file(task_id, filename):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                
                if task['status'] != 'completed':
                    return jsonify({"error": "翻译尚未完成"}), 400
                
                if not task['result_path'] or not os.path.exists(task['result_path']):
                    return jsonify({"error": "翻译结果不存在"}), 404
                
                # 根据filename参数决定返回哪个版本的翻译文件
                result_folder = os.path.join(RESULT_FOLDER, task_id)
                
                # 根据请求的文件名确定要返回的文件
                if filename == 'mono.pdf':
                    # 请求单语言版本
                    mono_filename = f"{task_id}_translated_mono.pdf"
                    mono_path = os.path.join(result_folder, mono_filename)
                    if os.path.exists(mono_path):
                        return send_from_directory(result_folder, mono_filename, as_attachment=False)
                elif filename == 'dual.pdf':
                    # 请求双语言版本
                    dual_filename = f"{task_id}_translated_dual.pdf"
                    dual_path = os.path.join(result_folder, dual_filename)
                    if os.path.exists(dual_path):
                        return send_from_directory(result_folder, dual_filename, as_attachment=False)
                
                # 如果找不到特定版本，返回默认结果
                return send_from_directory(
                    os.path.dirname(task['result_path']), 
                    os.path.basename(task['result_path']), 
                    as_attachment=False
                )
            
            @app.route('/api/tasks/<task_id>', methods=['GET'])
            def get_task(task_id):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                return jsonify({
                    "task_id": task['id'],
                    "filename": task['filename'],
                    "status": task['status'],
                    "message": task['message']
                })
            
            @app.route('/api/download/<task_id>', methods=['GET'])
            def download_result(task_id):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                
                if task['status'] != 'completed':
                    return jsonify({"error": "翻译尚未完成"}), 400
                
                if not task['result_path'] or not os.path.exists(task['result_path']):
                    return jsonify({"error": "结果文件不存在"}), 404
                
                result_dir = os.path.dirname(task['result_path'])
                result_filename = os.path.basename(task['result_path'])
                
                return send_from_directory(result_dir, result_filename, as_attachment=True)
            
            @app.route('/api/check_translation/<task_id>', methods=['GET'])
            def check_translation(task_id):
                """检查翻译状态"""
                if task_id not in tasks:
                    # 尝试从文件系统中恢复任务
                    try:
                        result_folder = os.path.join(RESULT_FOLDER, task_id)
                        translated_exist = os.path.exists(result_folder)
                        
                        if translated_exist:
                            # 查找翻译结果文件
                            dual_path = os.path.join(result_folder, f"{task_id}_translated_dual.pdf")
                            mono_path = os.path.join(result_folder, f"{task_id}_translated_mono.pdf")
                            
                            # 查找原始文件
                            uploads_dir = os.path.join(UPLOAD_FOLDER)
                            original_files = [f for f in os.listdir(uploads_dir) if f.startswith(f"{task_id}_")]
                            original_path = None
                            filename = None
                            
                            if original_files:
                                original_path = os.path.join(uploads_dir, original_files[0])
                                filename = original_files[0].replace(f"{task_id}_", "")
                            
                            # 恢复任务信息
                            if os.path.exists(dual_path) or os.path.exists(mono_path):
                                # 将任务添加到tasks字典
                                tasks[task_id] = {
                                    "id": task_id,
                                    "filename": filename or "未知文件",
                                    "original_path": original_path,
                                    "result_path": dual_path if os.path.exists(dual_path) else mono_path,
                                    "status": "completed",
                                    "message": "已从结果目录恢复任务"
                                }
                                
                                logger.info(f"从结果目录恢复了任务 {task_id}")
                                
                                return jsonify({
                                    "task_id": task_id,
                                    "status": "completed",
                                    "message": "翻译已完成"
                                })
                        
                        # 如果只有上传文件但没有翻译结果
                        uploads_dir = os.path.join(UPLOAD_FOLDER)
                        original_files = [f for f in os.listdir(uploads_dir) if f.startswith(f"{task_id}_")]
                        
                        if original_files:
                            original_path = os.path.join(uploads_dir, original_files[0])
                            filename = original_files[0].replace(f"{task_id}_", "")
                            
                            # 添加到tasks字典
                            tasks[task_id] = {
                                "id": task_id,
                                "filename": filename,
                                "original_path": original_path,
                                "result_path": None,
                                "status": "pending",
                                "message": "任务已创建"
                            }
                            
                            logger.info(f"从上传目录恢复了任务 {task_id}")
                            
                            return jsonify({
                                "task_id": task_id,
                                "status": "pending",
                                "message": "等待翻译"
                            })
                            
                        return jsonify({"error": "任务不存在"}), 404
                    except Exception as e:
                        logger.exception(f"尝试恢复任务 {task_id} 失败: {str(e)}")
                        return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                return jsonify({
                    "task_id": task_id,
                    "status": task['status'],
                    "message": task['message']
                })
            
            @app.route('/api/translated_files/<task_id>/exists', methods=['GET'])
            def check_translated_file(task_id):
                """检查翻译文件是否存在"""
                try:
                    result_folder = os.path.join(RESULT_FOLDER, task_id)
                    if not os.path.exists(result_folder):
                        return jsonify({"exists": False}), 404
                    
                    # 检查是否有翻译结果
                    dual_path = os.path.join(result_folder, f"{task_id}_translated_dual.pdf")
                    mono_path = os.path.join(result_folder, f"{task_id}_translated_mono.pdf")
                    
                    if os.path.exists(dual_path) or os.path.exists(mono_path):
                        return jsonify({"exists": True})
                    
                    return jsonify({"exists": False}), 404
                except Exception as e:
                    logger.exception(f"检查翻译文件 {task_id} 时出错: {str(e)}")
                    return jsonify({"error": str(e)}), 500
            
            @app.route('/api/latest_file', methods=['GET'])
            def get_latest_file():
                """获取最新上传的文件信息"""
                if not tasks:
                    # 尝试从结果目录获取文件信息
                    try:
                        result_dirs = os.listdir(RESULT_FOLDER)
                        if not result_dirs:
                            return jsonify({"error": "没有上传的文件"}), 404
                        
                        # 按照修改时间排序
                        result_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(RESULT_FOLDER, x)), reverse=True)
                        
                        # 检查第一个（最新的）目录
                        latest_dir = result_dirs[0]
                        latest_task_id = latest_dir
                        
                        # 查找是否有翻译文件
                        dual_path = os.path.join(RESULT_FOLDER, latest_dir, f"{latest_task_id}_translated_dual.pdf")
                        mono_path = os.path.join(RESULT_FOLDER, latest_dir, f"{latest_task_id}_translated_mono.pdf")
                        
                        # 如果没有找到文件，返回错误
                        if not (os.path.exists(dual_path) or os.path.exists(mono_path)):
                            return jsonify({"error": "未找到翻译文件"}), 404
                        
                        # 尝试找到原始文件
                        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
                        original_files = [f for f in os.listdir(uploads_dir) if f.startswith(latest_task_id)]
                        
                        filename = "unknown.pdf"
                        original_path = None
                        
                        if original_files:
                            original_path = os.path.join(uploads_dir, original_files[0])
                            filename = original_files[0].replace(f"{latest_task_id}_", "")
                        
                        # 将任务添加到tasks字典
                        tasks[latest_task_id] = {
                            "id": latest_task_id,
                            "filename": filename,
                            "original_path": original_path,
                            "result_path": dual_path if os.path.exists(dual_path) else mono_path,
                            "status": "completed",
                            "message": "已从结果目录恢复任务"
                        }
                        
                        logger.info(f"从结果目录恢复了最新任务 {latest_task_id}")
                        
                        # 返回任务信息
                        content_summary = {
                            "title": os.path.splitext(filename)[0],
                            "total_pages": "未知",
                            "has_abstract": False,
                            "sections_count": 0
                        }
                        
                        return jsonify({
                            "task_id": latest_task_id,
                            "filename": filename,
                            "status": "completed",
                            "content_summary": content_summary
                        })
                    except Exception as e:
                        logger.exception(f"从结果目录恢复任务出错: {str(e)}")
                        return jsonify({"error": "没有上传的文件"}), 404
                
                # 按照上传时间排序，获取最新的任务
                latest_task_id = None
                latest_task = None
                latest_time = 0
                
                for task_id, task in tasks.items():
                    # 获取文件的创建时间
                    try:
                        file_time = os.path.getctime(task['original_path']) if task['original_path'] else 0
                        if file_time > latest_time:
                            latest_time = file_time
                            latest_task_id = task_id
                            latest_task = task
                    except (OSError, KeyError):
                        continue
                
                if not latest_task_id:
                    return jsonify({"error": "无法确定最新文件"}), 404
                
                # 获取文件信息
                try:
                    # 这里可以添加更多的文件信息，如标题，页数等
                    content_summary = {
                        "title": os.path.splitext(latest_task['filename'])[0],
                        "total_pages": "未知",  # 这里可以用PyPDF2等工具获取实际页数
                        "has_abstract": False,
                        "sections_count": 0
                    }
                    
                    return jsonify({
                        "task_id": latest_task_id,
                        "filename": latest_task['filename'],
                        "status": latest_task['status'],
                        "content_summary": content_summary
                    })
                except Exception as e:
                    logger.exception(f"获取最新文件信息出错: {str(e)}")
                    return jsonify({"error": str(e)}), 500
            
            @app.route('/api/tasks', methods=['GET'])
            def list_tasks():
                """获取所有任务"""
                try:
                    # 先从内存中的tasks字典获取任务
                    task_list = []
                    for task_id, task in tasks.items():
                        task_list.append({
                            "task_id": task['id'],
                            "filename": task['filename'],
                            "status": task['status'],
                            "message": task['message'],
                            "created_at": task.get('created_at', time.time()),
                            "completed_at": task.get('completed_at')
                        })
                    
                    # 然后从文件系统中扫描所有任务，补充内存中未包含的任务
                    # 扫描上传目录
                    uploads_dir = os.path.join(UPLOAD_FOLDER)
                    if os.path.exists(uploads_dir):
                        for filename in os.listdir(uploads_dir):
                            if "_" in filename:  # 文件名格式应该是 "task_id_filename.pdf"
                                parts = filename.split("_", 1)
                                if len(parts) == 2:
                                    found_task_id = parts[0]
                                    original_filename = parts[1]
                                    
                                    # 如果这个任务不在内存中，添加它
                                    if found_task_id not in [t['task_id'] for t in task_list]:
                                        # 检查这个任务是否有翻译结果
                                        result_folder = os.path.join(RESULT_FOLDER, found_task_id)
                                        dual_path = os.path.join(result_folder, f"{found_task_id}_translated_dual.pdf")
                                        mono_path = os.path.join(result_folder, f"{found_task_id}_translated_mono.pdf")
                                        
                                        has_results = os.path.exists(dual_path) or os.path.exists(mono_path)
                                        
                                        file_path = os.path.join(uploads_dir, filename)
                                        file_stat = os.stat(file_path)
                                        
                                        task_list.append({
                                            "task_id": found_task_id,
                                            "filename": original_filename,
                                            "status": "completed" if has_results else "pending",
                                            "message": "翻译完成" if has_results else "等待翻译",
                                            "created_at": file_stat.st_ctime,
                                            "completed_at": None
                                        })
                    
                    # 扫描结果目录，可能有些任务的上传文件已被删除，但结果文件仍存在
                    results_dir = os.path.join(RESULT_FOLDER)
                    if os.path.exists(results_dir):
                        for task_id in os.listdir(results_dir):
                            result_folder = os.path.join(results_dir, task_id)
                            if os.path.isdir(result_folder):
                                # 如果这个任务不在任务列表中，添加它
                                if task_id not in [t['task_id'] for t in task_list]:
                                    # 检查是否有翻译结果
                                    dual_path = os.path.join(result_folder, f"{task_id}_translated_dual.pdf")
                                    mono_path = os.path.join(result_folder, f"{task_id}_translated_mono.pdf")
                                    
                                    if os.path.exists(dual_path) or os.path.exists(mono_path):
                                        # 获取文件时间
                                        file_path = dual_path if os.path.exists(dual_path) else mono_path
                                        file_stat = os.stat(file_path)
                                        
                                        task_list.append({
                                            "task_id": task_id,
                                            "filename": f"已恢复的文件_{task_id[:8]}.pdf",
                                            "status": "completed",
                                            "message": "翻译完成",
                                            "created_at": file_stat.st_ctime,
                                            "completed_at": file_stat.st_mtime
                                        })
                    
                    # 按创建时间排序，最新的在前面
                    task_list.sort(key=lambda x: x.get('created_at', 0), reverse=True)
                    
                    return jsonify({"tasks": task_list})
                except Exception as e:
                    logger.exception(f"获取任务列表时出错: {str(e)}")
                    return jsonify({"error": str(e)}), 500

            @app.route('/api/recent_files', methods=['GET'])
            def get_recent_files():
                """获取最近上传的文件"""
                try:
                    files = []
                    uploads_dir = os.path.join(UPLOAD_FOLDER)
                    
                    if not os.path.exists(uploads_dir):
                        return jsonify({"files": []}), 200
                    
                    for filename in os.listdir(uploads_dir):
                        if "_" in filename:  # 文件名格式应该是 "task_id_filename.pdf"
                            parts = filename.split("_", 1)
                            if len(parts) == 2:
                                task_id = parts[0]
                                original_name = parts[1]
                                
                                file_path = os.path.join(uploads_dir, filename)
                                file_stat = os.stat(file_path)
                                
                                files.append({
                                    "task_id": task_id,
                                    "filename": original_name,
                                    "created_time": file_stat.st_ctime,
                                    "modified_time": file_stat.st_mtime,
                                    "size": file_stat.st_size
                                })
                    
                    # 按修改时间排序，最新的在前面
                    files.sort(key=lambda x: x['modified_time'], reverse=True)
                    
                    return jsonify({"files": files})
                except Exception as e:
                    logger.exception(f"获取最近文件列表时出错: {str(e)}")
                    return jsonify({"error": str(e)}), 500
            
            logger.info(f"启动服务于端口 {args.port}")
            app.run(host='0.0.0.0', port=args.port)
            
        except ImportError:
            logger.error("无法导入Flask或CORS，请安装它们: pip install flask flask-cors")
            return 1

if __name__ == "__main__":
    import sys
    sys.exit(main()) 