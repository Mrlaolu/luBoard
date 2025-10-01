# app.py

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from data_parser import parse_contest_data, calculate_final_board_state
import copy

app = Flask(__name__)
app.secret_key = 'a-very-secret-key-for-session'

CONTEST_STATE = {
    "problem_ids": [],
    "initial_board": [],
    "all_submissions": [],
    "problems_info": {},
    "teams_map": {}
}

# 【功能修改】函数现在以总秒数作为参数
def calculate_board_at_time(total_seconds: int):
    current_board = copy.deepcopy(CONTEST_STATE["initial_board"])
    # 【功能修改】根据秒数筛选提交
    relevant_submissions = [s for s in CONTEST_STATE["all_submissions"] if s['time'] <= total_seconds]
    # 【功能修改】最后提交时间也用秒
    last_sub_times = { (sub['team_id'], sub['prob_id']): sub['time'] for sub in relevant_submissions }

    for team in current_board:
        current_solved = 0
        current_penalty = 0
        for pid, prob_info in team['status'].items():
            prob_info['last_submission_time'] = last_sub_times.get((team['team_id'], pid), -1)
            # 【功能修改】用秒来判断题目是否已解决
            if prob_info['final_is_ac'] and prob_info['final_solved_time'] <= total_seconds:
                attempts = prob_info['final_attempts_to_ac']
                prob_info['display'] = '+' + (str(attempts - 1) if attempts > 1 else '')
                # 【功能修改】前端显示的解决时间依然是分钟，保持榜单可读性
                prob_info['solved_time'] = prob_info['final_solved_time'] // 60
                prob_info['penalty'] = prob_info['final_penalty']
                current_solved += 1
                current_penalty += prob_info['final_penalty']
            # 【功能修改】用秒来判断是否有过提交
            elif prob_info['last_submission_time'] != -1 and prob_info['last_submission_time'] <= total_seconds:
                wa_attempts = sum(1 for sub in relevant_submissions if sub['team_id'] == team['team_id'] and sub['prob_id'] == pid and sub['status'] not in ('OK', 'AC'))
                if wa_attempts > 0: prob_info['display'] = '-' + str(wa_attempts)
        
        team['solved'] = current_solved
        team['penalty'] = current_penalty

    current_board.sort(key=lambda x: (-x['solved'], x['penalty']))
    rank, last_solved, last_penalty = 0, -1, -1
    for i, team in enumerate(current_board):
        if team['solved'] != last_solved or team['penalty'] != last_penalty: rank = i + 1
        team['rank'] = rank
        last_solved, last_penalty = team['solved'], team['penalty']

    problem_ids = CONTEST_STATE["problem_ids"]
    submissions_per_problem = {pid: sum(1 for sub in relevant_submissions if sub['prob_id'] == pid) for pid in problem_ids}
    stats = { 'Submitted': submissions_per_problem, 'Accepted': {pid: 0 for pid in problem_ids}, 'First Solved': {pid: float('inf') for pid in problem_ids} }
    
    for team in current_board:
        for pid, prob_info in team['status'].items():
            if '+' in prob_info['display']:
                stats['Accepted'][pid] += 1
                stats['First Solved'][pid] = min(stats['First Solved'][pid], prob_info.get('solved_time', float('inf')))

    formatted_stats = {}
    for row_name in ['Submitted', 'Accepted', 'First Solved']:
        formatted_stats[row_name] = {}
        for pid in problem_ids:
            if row_name in ['Submitted', 'Accepted']:
                count = stats[row_name][pid]
                total = stats['Submitted'].get(pid, 1)
                percent = f"({count / total * 100:.0f}%)" if total > 0 else "(0%)"
                formatted_stats[row_name][pid] = f"{count}<br><small>{percent}</small>"
            elif row_name == 'First Solved':
                time_val = stats[row_name][pid]
                formatted_stats[row_name][pid] = str(time_val) if time_val != float('inf') else "Null"
                
    return current_board, formatted_stats

def load_initial_data():
    try:
        problem_ids, initial_board, all_submissions, problems_info, teams_map = parse_contest_data('contest.dat')
        CONTEST_STATE["problem_ids"] = problem_ids
        CONTEST_STATE["initial_board"] = initial_board
        CONTEST_STATE["all_submissions"] = sorted(all_submissions, key=lambda x: x['time'])
        CONTEST_STATE["problems_info"] = problems_info
        CONTEST_STATE["teams_map"] = teams_map
        print("比赛数据加载成功！")
    except FileNotFoundError:
        print("错误：contest.dat 文件未找到！")

load_initial_data()

@app.route('/')
def scoreboard_page(): return render_template('index.html')

@app.route('/api/initial_data')
def api_initial_data():
    # 【功能修改】返回总秒数
    return jsonify({
        'problems': CONTEST_STATE["problem_ids"], 
        'total_duration_sec': 300 * 60 
    })

# 【功能修改】API路由和参数都改为秒
@app.route('/api/board_at_time/<int:seconds>')
def api_board_at_time(seconds):
    board_data, stats_data = calculate_board_at_time(seconds)
    return jsonify({'board': board_data, 'statistics': stats_data})

@app.route('/update', methods=['GET', 'POST'])
def update_submission():
    if request.method == 'POST':
        session['selected_team_id'] = int(request.form['team_id'])
        prob_id = request.form['problem_id']
        result = request.form['result']
        new_submission = { 'team_id': int(request.form['team_id']), 'prob_id': prob_id, 'status': 'AC' if result == 'AC' else 'WA' }
        if result == 'AC':
            try: solved_time_min = int(request.form.get('solved_time_min', 0))
            except (ValueError, TypeError): solved_time_min = 0
            new_submission['time'] = solved_time_min * 60
        else:
            try: wa_time_min = int(request.form.get('solved_time_min', 1)) - 1
            except (ValueError, TypeError): wa_time_min = 0
            new_submission['time'] = wa_time_min * 60

        CONTEST_STATE["all_submissions"].append(new_submission)
        CONTEST_STATE["all_submissions"].sort(key=lambda x: x['time'])
        print(f"新提交已注入: {new_submission}")
        
        _, new_initial_board = calculate_final_board_state(
            CONTEST_STATE["teams_map"],
            CONTEST_STATE["problems_info"],
            CONTEST_STATE["all_submissions"]
        )
        CONTEST_STATE["initial_board"] = new_initial_board
        print("全局最终状态已刷新！")
        
        return redirect(url_for('update_submission'))
    
    selected_team_id = session.pop('selected_team_id', None)
    return render_template('update.html', 
                           teams=CONTEST_STATE["initial_board"], 
                           problems=CONTEST_STATE["problem_ids"],
                           selected_team_id=selected_team_id)

@app.route('/add_team', methods=['POST'])
def add_team():
    new_team_name = request.form.get('team_name')
    if new_team_name:
        max_id = max(CONTEST_STATE["teams_map"].keys()) if CONTEST_STATE["teams_map"] else 0
        new_id = max_id + 1
        CONTEST_STATE["teams_map"][new_id] = {'id': new_id, 'school': 'N/A', 'name': new_team_name}

        _, new_initial_board = calculate_final_board_state(
            CONTEST_STATE["teams_map"],
            CONTEST_STATE["problems_info"],
            CONTEST_STATE["all_submissions"]
        )
        CONTEST_STATE["initial_board"] = new_initial_board
        print(f"新队伍已添加并刷新榜单: {new_team_name}")

    return redirect(url_for('update_submission'))

if __name__ == '__main__':
    app.run(port=5000) # 指定在5000端口上运行应用