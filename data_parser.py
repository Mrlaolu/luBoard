import re

def parse_contest_data(filepath='contest.dat'):
    """
    解析 contest.dat 文件，并返回比赛信息和榜单数据。
    这个版本生成了前端需要的包含单题罚时的详细数据结构。
    """
    problems = {}
    teams = {}
    submissions = []
    submissions_per_problem = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('@p'):
                parts = line.split(' ', 1)
                if len(parts) == 2 and parts[1].count(',') == 3:
                    p_id, p_name, penalty_time, _ = parts[1].split(',')
                    problems[p_id] = {'name': p_name, 'penalty_time': int(penalty_time)}
            
            elif line.startswith('@t'):
                if line.count(',') >= 3:
                    team_id_str, _, _, team_info_str = line.split(',', 3)
                    if ' ' in team_id_str:
                        team_id = int(team_id_str.split(' ')[1])
                        match = re.match(r'"(.*?)\s-\s(.*?)(?:\s-\s.*)?"', team_info_str)
                        if match:
                            school, team_name = match.groups()
                        else:
                            school = ""
                            team_name = team_info_str.strip('"')

                        # 保留你增加的过滤逻辑，这是个好主意！
                        if team_name != 'Пополнить команду':
                            teams[team_id] = {
                                'id': team_id, 'school': school, 'name': team_name, 'solved': 0, 'penalty': 0,
                                'status': {p_id: {'attempts': 0, 'solved_time': 0, 'is_ac': False} for p_id in problems}
                            }
            
            elif line.startswith('@s'):
                parts = line.split(' ', 1)
                if len(parts) == 2 and parts[1].count(',') == 4:
                    team_id, prob_id, num_attempts, time, status = parts[1].split(',')
                    submissions.append({
                        'team_id': int(team_id), 'prob_id': prob_id, 'time': int(time), 'status': status
                    })
                    submissions_per_problem[prob_id] = submissions_per_problem.get(prob_id, 0) + 1

    # --- 数据处理部分 ---
    submissions.sort(key=lambda x: x['time'])

    for sub in submissions:
        team_id = sub['team_id']
        prob_id = sub['prob_id']
        if team_id not in teams or prob_id not in problems:
            continue
        team = teams[team_id]
        prob_status = team['status'][prob_id]
        
        if 'penalty' not in prob_status:
            prob_status['penalty'] = 0

        if not prob_status['is_ac']:
            if sub['status'] in ('OK', 'AC'):
                prob_status['is_ac'] = True
                solved_time_in_minutes = sub['time'] // 60
                prob_status['solved_time_min'] = solved_time_in_minutes
                team['solved'] += 1
                penalty_per_problem = problems[prob_id]['penalty_time']
                problem_penalty = (sub['time'] // 60) + prob_status['attempts'] * penalty_per_problem
                prob_status['penalty'] = problem_penalty
                team['penalty'] += problem_penalty
            else:
                prob_status['attempts'] += 1

    # --- 最终数据格式化 ---
    board_list = list(teams.values())
    board_list.sort(key=lambda x: (-x['solved'], x['penalty']))
    
    final_board = []
    rank = 0
    last_solved = -1
    last_penalty = -1

    for i, team in enumerate(board_list):
        if team['solved'] != last_solved or team['penalty'] != last_penalty:
            rank = i + 1
        last_solved = team['solved']
        last_penalty = team['penalty']
        
        status_display = {}
        for p_id in sorted(problems.keys()):
            p_info = team['status'].get(p_id)
            solved_time_val = 0
            display_text = ""
            penalty_val = 0
            
            if p_info:
                if p_info['is_ac']:
                    display_text = '+' + (str(p_info['attempts']) if p_info['attempts'] > 0 else '')
                    solved_time_val = p_info.get('solved_time_min', 0)
                    penalty_val = p_info.get('penalty', 0)
                elif p_info['attempts'] > 0:
                    display_text = '-' + str(p_info['attempts'])

            status_display[p_id] = {
                'display': display_text,
                'solved_time': solved_time_val,
                'penalty': penalty_val
            }

        final_board.append({
            'team_id': team['id'],  # <--- 【核心修改】把原始的、唯一的ID加进来！
            'rank': rank,
            'team': f"{team['school']} - {team['name']}" if team['school'] else team['name'],
            'solved': team['solved'],
            'penalty': team['penalty'],
            'status': status_display
        })

    problem_ids = sorted(problems.keys())

    return problem_ids, final_board, submissions_per_problem