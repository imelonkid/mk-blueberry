import os
import json
import time
from typing import Dict, List, Any, Union, Literal
import openai
from openai import OpenAI
import requests
import logging

class Translator:
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo", provider: str = "openai"):
        """
        初始化翻译器
        
        参数:
            api_key: API密钥，如果为None，则尝试从环境变量获取
            model: 使用的模型名称
            provider: API提供商，可以是"openai"或"deepseek"
        """
        self.provider = provider.lower()
        
        # 如果未提供API密钥，则尝试从环境变量获取
        if api_key is None:
            if self.provider == "openai":
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("未提供OpenAI API密钥，请提供API密钥或设置OPENAI_API_KEY环境变量")
            elif self.provider == "deepseek":
                api_key = os.environ.get("DEEPSEEK_API_KEY")
                if not api_key:
                    raise ValueError("未提供DeepSeek API密钥，请提供API密钥或设置DEEPSEEK_API_KEY环境变量")
            else:
                raise ValueError(f"不支持的提供商: {provider}，目前支持 'openai' 或 'deepseek'")
        
        self.api_key = api_key
        self.model = model
        
        # 初始化相应的客户端
        if self.provider == "openai":
            self.client = OpenAI(api_key=api_key)
        elif self.provider == "deepseek":
            # DeepSeek使用REST API，不需要客户端实例
            self.deepseek_api_url = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
    
    def translate_text(self, text: str, target_language: str = "中文") -> str:
        """
        翻译单个文本
        
        参数:
            text: 要翻译的文本
            target_language: 目标语言
            
        返回:
            翻译后的文本
        """
        if not text or text.strip() == "":
            return ""
        
        logging.info(f"翻译文本，长度: {len(text)}, 提供商: {self.provider}, 模型: {self.model}")
        
        # 构建翻译提示
        prompt = f"""请将以下文本翻译成{target_language}，保持原始格式和专业术语的准确性：
        
{text}

翻译:"""
        
        system_message = f"你是一个专业的学术翻译器，专注于将学术论文翻译成{target_language}。保持专业术语的准确性，并使翻译流畅自然。"
        
        try:
            if self.provider == "openai":
                return self._translate_with_openai(prompt, system_message)
            elif self.provider == "deepseek":
                return self._translate_with_deepseek(prompt, system_message)
        except Exception as e:
            logging.error(f"翻译时发生错误: {str(e)}", exc_info=True)
            return f"翻译失败: {str(e)}"
    
    def _translate_with_openai(self, prompt: str, system_message: str) -> str:
        """使用OpenAI API进行翻译"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # 较低的温度，提高一致性
            max_tokens=4096,  # 最大令牌数
        )
        
        # 获取翻译结果
        translated_text = response.choices[0].message.content.strip()
        return translated_text
    
    def _translate_with_deepseek(self, prompt: str, system_message: str) -> str:
        """使用DeepSeek API进行翻译"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 确保model参数值正确，默认使用deepseek-chat模型
        model_name = self.model if self.model else "deepseek-chat"
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.deepseek_api_url,
                headers=headers,
                json=payload
            )
            
            # 调试输出
            print(f"DeepSeek API请求参数: {json.dumps(payload, ensure_ascii=False)}")
            print(f"DeepSeek API响应状态: {response.status_code}")
            
            # 如果响应状态码不是200，输出错误详情
            if response.status_code != 200:
                print(f"DeepSeek API错误: {response.text}")
                return f"翻译失败: API返回{response.status_code}错误 - {response.text}"
            
            # 解析响应
            response_data = response.json()
            translated_text = response_data["choices"][0]["message"]["content"].strip()
            return translated_text
            
        except Exception as e:
            print(f"DeepSeek API调用异常: {str(e)}")
            return f"翻译错误: {str(e)}"
    
    def translate_paragraphs(self, paragraphs: List[str], target_language: str = "中文") -> List[Dict[str, str]]:
        """
        翻译段落列表，并返回原文和译文的对照
        
        参数:
            paragraphs: 段落列表
            target_language: 目标语言
            
        返回:
            包含原文和译文的字典列表
        """
        result = []
        
        for paragraph in paragraphs:
            # 过滤空段落
            if not paragraph or paragraph.strip() == "":
                continue
                
            # 翻译段落
            translated = self.translate_text(paragraph, target_language)
            
            # 添加到结果
            result.append({
                "original": paragraph,
                "translated": translated
            })
            
            # 为避免API请求过快，添加短暂延迟
            time.sleep(0.5)
        
        return result
    
    def translate_structured_content(self, content: Dict[str, Any], target_language: str = "中文") -> Dict[str, Any]:
        """
        翻译结构化内容（如标题、摘要、章节等）
        
        参数:
            content: 结构化内容字典
            target_language: 目标语言
            
        返回:
            翻译后的结构化内容
        """
        result = {
            "original": content,
            "translated": {}
        }
        
        translated_content = result["translated"]
        
        # 翻译标题
        if "title" in content and content["title"]:
            translated_content["title"] = self.translate_text(content["title"], target_language)
        
        # 翻译摘要
        if "abstract" in content and content["abstract"]:
            translated_content["abstract"] = self.translate_text(content["abstract"], target_language)
        
        # 翻译章节
        if "sections" in content and content["sections"]:
            translated_content["sections"] = []
            
            for section in content["sections"]:
                translated_section = {
                    "title": self.translate_text(section["title"], target_language),
                    "content": self.translate_paragraphs(section["content"], target_language)
                }
                
                translated_content["sections"].append(translated_section)
        
        return result
    
    def translate_document(self, document: Dict[str, Any], target_language: str = "中文") -> Dict[str, Any]:
        """
        翻译整个文档
        
        参数:
            document: 文档字典
            target_language: 目标语言
            
        返回:
            翻译后的文档
        """
        result = {
            "metadata": document.get("metadata", {}),
            "total_pages": document.get("total_pages", 0)
        }
        
        # 翻译内容
        if "content" in document:
            result["content"] = self.translate_structured_content(document["content"], target_language)
        
        return result


def translate_pdf_content(content_json: str, target_language: str = "中文", api_key: str = None, provider: str = "openai", model: str = None) -> str:
    """
    翻译PDF内容
    
    参数:
        content_json: PDF内容的JSON字符串
        target_language: 目标语言
        api_key: API密钥
        provider: API提供商，可以是"openai"或"deepseek"
        model: 使用的模型名称
        
    返回:
        翻译后的内容JSON字符串
    """
    # 解析内容JSON
    content = json.loads(content_json)
    
    # 设置默认模型
    if model is None:
        if provider.lower() == "openai":
            model = "gpt-3.5-turbo"
        elif provider.lower() == "deepseek":
            model = "deepseek-chat"
    
    # 初始化翻译器
    translator = Translator(api_key=api_key, model=model, provider=provider)
    
    # 翻译文档
    translated_content = translator.translate_document(content, target_language)
    
    # 返回翻译后的内容
    return json.dumps(translated_content, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="翻译PDF内容")
    parser.add_argument("input_file", help="输入JSON文件路径")
    parser.add_argument("--output", "-o", help="输出JSON文件路径")
    parser.add_argument("--language", "-l", default="中文", help="目标语言")
    parser.add_argument("--api-key", "-k", help="API密钥")
    parser.add_argument("--provider", "-p", default="openai", choices=["openai", "deepseek"], help="API提供商")
    parser.add_argument("--model", "-m", help="使用的模型名称")
    
    args = parser.parse_args()
    
    try:
        # 读取输入文件
        with open(args.input_file, "r", encoding="utf-8") as f:
            content_json = f.read()
        
        # 翻译内容
        translated_json = translate_pdf_content(
            content_json, 
            args.language, 
            args.api_key, 
            args.provider, 
            args.model
        )
        
        # 输出结果
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(translated_json)
            print(f"翻译结果已保存到: {args.output}")
        else:
            print(translated_json)
            
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1) 