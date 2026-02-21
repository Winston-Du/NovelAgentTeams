#!/usr/bin/env python
import sys
import warnings
import os

from datetime import datetime

from novels_project.crew import NovelsProject

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# 支持的模型列表
SUPPORTED_MODELS = ['gemini-3-pro', 'gpt-5.2','qwen3-max','deepseek-v3.2-exp']

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    可选参数：--model [gemini-3-pro|gpt-5.2]
    """
    # 从环境变量或命令行参数获取模型名称
    model_name = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--model' and len(sys.argv) > 2:
            model_name = sys.argv[2]
            if model_name not in SUPPORTED_MODELS:
                raise ValueError(f"不支持的模型: {model_name}。支持的模型: {SUPPORTED_MODELS}")

    inputs = {
        'topic': 'AI LLMs',
        'current_year': str(datetime.now().year)
    }

    try:
        crew = NovelsProject(model_name=model_name)
        crew.crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    用法: train <iterations> <filename> [--model model_name]
    """
    model_name = None
    n_iterations = None
    filename = None

    # 解析命令行参数
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--model' and i + 1 < len(sys.argv):
            model_name = sys.argv[i + 1]
            i += 2
        else:
            if n_iterations is None:
                n_iterations = int(sys.argv[i])
            elif filename is None:
                filename = sys.argv[i]
            i += 1

    if model_name and model_name not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型: {model_name}。支持的模型: {SUPPORTED_MODELS}")

    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        crew = NovelsProject(model_name=model_name)
        crew.crew().train(n_iterations=n_iterations, filename=filename, inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    用法: replay <task_id> [--model model_name]
    """
    model_name = None
    task_id = None

    # 解析命令行参数
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--model' and i + 2 < len(sys.argv):
            model_name = sys.argv[i + 2]
        elif not arg.startswith('--'):
            task_id = arg

    if model_name and model_name not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型: {model_name}。支持的模型: {SUPPORTED_MODELS}")

    try:
        crew = NovelsProject(model_name=model_name)
        crew.crew().replay(task_id=task_id)

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    用法: test <iterations> <eval_llm> [--model model_name]
    """
    model_name = None
    n_iterations = None
    eval_llm = None

    # 解析命令行参数
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--model' and i + 1 < len(sys.argv):
            model_name = sys.argv[i + 1]
            i += 2
        else:
            if n_iterations is None:
                n_iterations = int(sys.argv[i])
            elif eval_llm is None:
                eval_llm = sys.argv[i]
            i += 1

    if model_name and model_name not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型: {model_name}。支持的模型: {SUPPORTED_MODELS}")

    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }

    try:
        crew = NovelsProject(model_name=model_name)
        crew.crew().test(n_iterations=n_iterations, eval_llm=eval_llm, inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

def run_with_trigger():
    """
    Run the crew with trigger payload.
    用法: run_with_trigger <json_payload> [--model model_name]
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    model_name = None
    payload_str = None

    # 解析命令行参数
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--model' and i + 2 < len(sys.argv):
            model_name = sys.argv[i + 2]
        elif not arg.startswith('--'):
            payload_str = arg

    if model_name and model_name not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型: {model_name}。支持的模型: {SUPPORTED_MODELS}")

    try:
        trigger_payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",
        "current_year": ""
    }

    try:
        crew = NovelsProject(model_name=model_name)
        result = crew.crew().kickoff(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
