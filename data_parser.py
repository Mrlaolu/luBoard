# data_parser.py

import re

def calculate_final_board_state(teams, problems, submissions):
    """
    【重构版】根据当前的队伍、题目和提交列表，计算最终的榜单状态。
    所有时间相关的字段（如 solved_time, effective_last_sub_time）都以“秒”为单位。
    """
    submissions.sort(key=lambda x: x['time'])

    total_attempts_map = {}
    for sub in submissions:
        key = (sub['team_id'], sub['prob_id'])
        total_attempts_map[key] = total_attempts_map.get(key, 0) + 1

    final_statuses = {}
    for sub in submissions:
        team_id, prob_id = sub['team_id'], sub['prob_id']
        if team_id not in teams or prob_id not in problems:
            continue

        team_prob_key = (team_id, prob_id)
        if team_prob_key not in final_statuses:
            final_statuses[team_prob_key] = {
                'attempts_before_ac': 0, 'is_ac': False, 'solved_time': -1, 
                'penalty': 0, 'effective_last_sub_time': -1 
            }
        
        status = final_statuses[team_prob_key]
        
        if not status['is_ac']:
            # 【功能修改】记录最后提交时间，单位为秒
            status['effective_last_sub_time'] = sub['time']
            if sub['status'] in ('OK', 'AC'):
                status['is_ac'] = True
                # 【功能修改】记录AC时间，单位为秒
                status['solved_time'] = sub['time']
                penalty_per_wa = problems[prob_id]['penalty_time']
                # 【功能修改】罚时计算基于分钟，所以这里要进行转换
                solved_time_min = sub['time'] // 60
                status['penalty'] = solved_time_min + status['attempts_before_ac'] * penalty_per_wa
            else:
                status['attempts_before_ac'] += 1

    initial_board = []
    problem_ids = sorted(problems.keys())
    for team_id, team_info in teams.items():
        team_status = {}
        for p_id in problem_ids:
            final_status = final_statuses.get((team_id, p_id), 
                                              {'attempts_before_ac': 0, 'is_ac': False, 'solved_time': -1, 
                                               'penalty': 0, 'effective_last_sub_time': -1})
            total_raw_attempts = total_attempts_map.get((team_id, p_id), 0)

            team_status[p_id] = {
                'display': '', 'solved_time': 0, 'penalty': 0, 'last_submission_time': -1,
                'final_is_ac': final_status['is_ac'],
                # 【功能修改】所有 'final_' 时间字段现在都以秒为单位
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
    【重构版】仅负责从文件读取原始数据，然后调用核心计算函数。
    """
    problems = {}
    teams = {}
    submissions = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                if line.startswith('@p'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2 and parts[1].count(',') == 3:
                        p_id, _, penalty_time, _ = parts[1].split(',')
                        problems[p_id] = {'name': p_id, 'penalty_time': int(penalty_time)}
                elif line.startswith('@t'):
                    if line.count(',') >= 3:
                        team_id_str, _, _, team_info_str = line.split(',', 3)
                        if ' ' in team_id_str:
                            team_id = int(team_id_str.split(' ')[1])
                            match = re.match(r'"(.*?)\s-\s(.*?)(?:\s-\s.*)?"', team_info_str)
                            if match: school, team_name = match.groups()
                            else: school, team_name = "", team_info_str.strip('"')
                            if team_name != 'Пополнить команду':
                                teams[team_id] = {'id': team_id, 'school': school, 'name': team_name}
                elif line.startswith('@s'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2 and parts[1].count(',') == 4:
                        team_id, prob_id, _, time, status = parts[1].split(',')
                        submissions.append({'team_id': int(team_id), 'prob_id': prob_id, 'time': int(time), 'status': status})
    except FileNotFoundError:
        return [], [], [], {}, {}

    problem_ids, initial_board = calculate_final_board_state(teams, problems, submissions)
    
    return problem_ids, initial_board, submissions, problems, teams