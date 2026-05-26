# -*- coding: utf-8 -*-
"""
用户交互模块 - 提供命令行菜单选择和手动输入功能
"""
import sys


def is_interactive():
    """检测是否处于交互模式（不是管道输入）"""
    return sys.stdin.isatty()


def select_from_results(results, title="选择结果"):
    """
    显示多结果选择菜单

    参数:
        results: 结果列表，每个元素是字典
        title: 菜单标题

    返回:
        选中的结果字典，或 None（取消）
    """
    if not results:
        return None

    # 如果只有一个结果，直接返回
    if len(results) == 1:
        return results[0]

    # 非交互模式返回第一个结果
    if not is_interactive():
        return results[0]

    print(f"\n=== {title} ===")
    for i, r in enumerate(results, 1):
        # 显示标题和年份
        item_title = r.get('title', r.get('name', 'Unknown'))
        item_year = r.get('year', '')
        item_rating = r.get('rating', '')
        if item_rating:
            print(f"  [{i}] {item_title} ({item_year}) - 评分: {item_rating}")
        else:
            print(f"  [{i}] {item_title} ({item_year})")
    print(f"  [0] 取消")

    try:
        choice = input("选择: ").strip()
        if choice == '0' or not choice:
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            return results[idx]
    except (ValueError, EOFError):
        pass

    return None


def manual_input(title="手动输入搜索关键词"):
    """
    当搜索失败时，让用户手动输入关键词重试

    参数:
        title: 提示标题

    返回:
        用户输入的关键词，或 None（取消）
    """
    if not is_interactive():
        return None

    print(f"\n=== {title} ===")
    try:
        keyword = input("输入搜索关键词 (直接回车取消): ").strip()
        return keyword if keyword else None
    except (EOFError, KeyboardInterrupt):
        return None


def manual_metadata_input():
    """
    手动输入完整电影/剧集资料

    返回:
        包含手动输入资料的字典，或 None（取消）
    """
    if not is_interactive():
        return None

    print("\n=== 手动输入资料 ===")
    try:
        title = input("片名: ").strip()
        if not title:
            return None

        year = input("年份 (选填): ").strip()
        plot = input("简介 (选填): ").strip()
        rating = input("评分 (选填): ").strip()

        result = {
            'title': title,
            'year': year if year else None,
            'plot': plot,
        }

        if rating:
            try:
                result['rating'] = float(rating)
            except ValueError:
                result['rating'] = None
        else:
            result['rating'] = None

        return result
    except (EOFError, KeyboardInterrupt):
        return None


def confirm_action(message, default=False):
    """
    确认操作提示

    参数:
        message: 确认消息
        default: 默认选项（True/False）

    返回:
        bool - 用户确认返回 True，取消返回 False
    """
    if not is_interactive():
        return default

    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        response = input(message + suffix).strip().lower()
        if not response:
            return default
        return response in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return False