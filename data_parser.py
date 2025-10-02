"""
该模块负责解析比赛数据文件 (`contest.dat`) 并计算榜单状态。

主要功能:
1. `parse_contest_data`: 读取和解析 `contest.dat` 文件，提取出题目、
   队伍和提交记录的原始数据。
2. `calculate_final_board_state`: 作为核心计算引擎，根据原始数据
   计算出每个队伍在比赛结束时的最终状态，包括每道题的通过情况、
   罚时、尝试次数等。所有时间单位在此模块内部统一处理为“秒”。
"""

import re

def calculate_final_board_state(teams, problems, submissions):
    """
    根据给定的队伍、题目和提交列表，计算最终的榜单状态。

    此函数是整个榜单系统的数据处理核心。它处理所有提交，确定每个队伍
    每道题的最终状态（是否AC，AC时间，罚时等）。所有内部时间计算都以
    “秒”为单位，以保证精度。

    Args:
        teams (dict): 队伍信息字典，键为 team_id。
        problems (dict): 题目信息字典，键为 prob_id。
        submissions (list): 包含所有提交记录的列表。

    Returns:
        tuple:
            - problem_ids (list): 排序后的题目ID列表。
            - initial_board (list): 包含每个队伍最终状态的完整榜单数据结构。
              这个“初始榜单”实际上是比赛结束时的最终榜单，作为后续按时间点
              回放的基础。
    """
    # 按提交时间对所有提交记录进行排序，这是正确处理状态变化的前提
    submissions.sort(key=lambda x: x['time'])

    # 预计算每个队伍每道题的总提交次数
    total_attempts_map = {}
    for sub in submissions:
        key = (sub['team_id'], sub['prob_id'])
        total_attempts_map[key] = total_attempts_map.get(key, 0) + 1

    # 存储每个队伍每道题的最终解决状态
    final_statuses = {}
    for sub in submissions:
        team_id, prob_id = sub['team_id'], sub['prob_id']
        # 忽略无效的提交数据
        if team_id not in teams or prob_id not in problems:
            continue

        team_prob_key = (team_id, prob_id)
        # 如果是该队伍该题的第一次提交，则初始化状态
        if team_prob_key not in final_statuses:
            final_statuses[team_prob_key] = {
                'attempts_before_ac': 0, 'is_ac': False, 'solved_time': -1, 
                'penalty': 0, 'effective_last_sub_time': -1 
            }
        
        status = final_statuses[team_prob_key]
        
        # 只有在题目尚未被AC时，才处理新的提交
        if not status['is_ac']:
            status['effective_last_sub_time'] = sub['time'] # 记录最后一次提交时间（秒）
            if sub['status'] in ('OK', 'AC'):
                # 首次AC
                status['is_ac'] = True
                status['solved_time'] = sub['time'] # 记录AC时间（秒）
                penalty_per_wa = problems[prob_id]['penalty_time']
                solved_time_min = sub['time'] // 60 # 罚时计算基于分钟
                status['penalty'] = solved_time_min + status['attempts_before_ac'] * penalty_per_wa
            else:
                # 是一次错误尝试
                status['attempts_before_ac'] += 1

    # 构建最终榜单数据结构
    initial_board = []
    problem_ids = sorted(problems.keys())
    for team_id, team_info in teams.items():
        team_status = {}
        for p_id in problem_ids:
            # 获取该题的最终状态，如果无提交则使用默认状态
            final_status = final_statuses.get((team_id, p_id), 
                                              {'attempts_before_ac': 0, 'is_ac': False, 'solved_time': -1, 
                                               'penalty': 0, 'effective_last_sub_time': -1})
            total_raw_attempts = total_attempts_map.get((team_id, p_id), 0)

            # 组装前端所需的所有最终状态字段，以 'final_' 为前缀
            team_status[p_id] = {
                'display': '', 'solved_time': 0, 'penalty': 0, 'last_submission_time': -1,
                'final_is_ac': final_status['is_ac'],
                'final_solved_time': final_status['solved_time'],
                'final_penalty': final_status['penalty'],
                'final_attempts_to_ac': final_status['attempts_before_ac'] + 1 if final_status['is_ac'] else final_status['attempts_before_ac'],
                'final_effective_last_sub_time': final_status['effective_last_sub_time'], 
                'final_total_attempts': total_raw_attempts 
            }

        initial_board.append({
            'team_id': team_id, 'rank': 0,
            'team': f"{team_info['school']} - {team_info['name']}" if team_info['school'] else team_info['name'],
            'solved': 0, 'penalty': 0, 'status': team_status
        })
        
    return problem_ids, initial_board

def parse_contest_data(filepath='contest.dat'):
    """
    解析 `contest.dat` 文件，提取题目、队伍和提交的原始信息。

    该函数作为数据入口，负责读取文件并将其内容解析成结构化的数据，
    然后调用 `calculate_final_board_state` 来完成核心的榜单计算。

    Args:
        filepath (str): 比赛数据文件的路径。

    Returns:
        tuple:
            - problem_ids (list): 题目ID列表。
            - initial_board (list): 计算出的最终榜单。
            - submissions (list): 原始提交记录列表。
            - problems (dict): 原始题目信息字典。
            - teams (dict): 原始队伍信息字典。
            如果文件未找到，则返回包含空数据结构的元组。
    """
    problems = {}
    teams = {}
    submissions = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                # 解析题目信息行
                if line.startswith('@p'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2 and parts[1].count(',') == 3:
                        p_id, _, penalty_time, _ = parts[1].split(',')
                        problems[p_id] = {'name': p_id, 'penalty_time': int(penalty_time)}
                # 解析队伍信息行
                elif line.startswith('@t'):
                    if line.count(',') >= 3:
                        team_id_str, _, _, team_info_str = line.split(',', 3)
                        if ' ' in team_id_str:
                            team_id = int(team_id_str.split(' ')[1])
                            match = re.match(r'"(.*?)\s-\s(.*?)(?:\s-\s.*)?"', team_info_str)
                            if match: school, team_name = match.groups()
                            else: school, team_name = "", team_info_str.strip('"')
                            if team_name != 'Пополнить команду': # 过滤特定占位队伍
                                teams[team_id] = {'id': team_id, 'school': school, 'name': team_name}
                # 解析提交记录行
                elif line.startswith('@s'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2 and parts[1].count(',') == 4:
                        team_id, prob_id, _, time, status = parts[1].split(',')
                        submissions.append({'team_id': int(team_id), 'prob_id': prob_id, 'time': int(time), 'status': status})
    except FileNotFoundError:
        return [], [], [], {}, {}

    # 调用核心计算函数，生成最终榜单
    problem_ids, initial_board = calculate_final_board_state(teams, problems, submissions)
    
    return problem_ids, initial_board, submissions, problems, teams