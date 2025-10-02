"""
这是一个基于 Flask 的 Web 应用，用于实时回放编程竞赛的榜单变化。

核心功能:
- 从 `contest.dat` 文件加载比赛的初始配置和所有提交数据。
- 提供一个 Web 界面 (`/`)，通过时间轴拖动或自动播放来展示任何时刻的榜单状态。
- 提供 API 接口 (`/api/...`)，用于前端获取题目信息、榜单数据等。
- 提供一个后台控制面板 (`/update`)，允许管理员手动添加新的提交记录或队伍，并实时刷新比赛状态。
- 支持定时启动功能，可以在预设的时间自动开始播放比赛进程。
"""

import copy
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from data_parser import parse_contest_data, calculate_final_board_state

# 初始化 Flask 应用
app = Flask(__name__)
# 设置 session 密钥，用于在请求之间安全地存储数据
app.secret_key = 'a-very-secret-key-for-session'

# 全局变量，用于存储整个比赛的状态信息
CONTEST_STATE = {
    "problem_ids": [],      # 题目ID列表
    "initial_board": [],    # 计算出的最终榜单状态，作为回放的基准
    "all_submissions": [],  # 所有的提交记录
    "problems_info": {},    # 题目的详细信息（如罚时）
    "teams_map": {}         # 队伍ID到队伍信息的映射
}

def calculate_board_at_time(total_seconds: int):
    """
    根据给定的总秒数，计算并生成那一时刻的榜单状态。

    此函数是比赛回放的核心逻辑。它基于初始榜单状态，通过筛选在指定时间点
    之前发生的所有提交，重新计算每个队伍的解题数、罚时和排名。

    Args:
        total_seconds (int): 从比赛开始经过的总秒数。

    Returns:
        tuple: 包含两个元素的元组。
               - current_board (list): 当前时刻的榜单数据列表。
               - formatted_stats (dict): 当前时刻的题目统计数据。
    """
    # 深拷贝初始榜单，以避免修改全局状态
    current_board = copy.deepcopy(CONTEST_STATE["initial_board"])
    
    # 筛选出在指定时间点之前的所有提交记录
    relevant_submissions = [s for s in CONTEST_STATE["all_submissions"] if s['time'] <= total_seconds]
    
    # 计算每个队伍每个题目的最后一次提交时间（秒）
    last_sub_times = { (sub['team_id'], sub['prob_id']): sub['time'] for sub in relevant_submissions }

    # 遍历榜单上的每个队伍，更新其状态
    for team in current_board:
        current_solved = 0
        current_penalty = 0
        for pid, prob_info in team['status'].items():
            # 更新该题的最后提交时间
            prob_info['last_submission_time'] = last_sub_times.get((team['team_id'], pid), -1)
            
            # 如果题目最终是AC状态，且AC时间早于或等于当前时间点
            if prob_info['final_is_ac'] and prob_info['final_solved_time'] <= total_seconds:
                attempts = prob_info['final_attempts_to_ac']
                prob_info['display'] = '+' + (str(attempts - 1) if attempts > 1 else '')
                prob_info['solved_time'] = prob_info['final_solved_time'] // 60 # 前端显示分钟
                prob_info['penalty'] = prob_info['final_penalty']
                current_solved += 1
                current_penalty += prob_info['final_penalty']
            # 如果题目未AC，但在此时间点前有过提交
            elif prob_info['last_submission_time'] != -1 and prob_info['last_submission_time'] <= total_seconds:
                wa_attempts = sum(1 for sub in relevant_submissions if sub['team_id'] == team['team_id'] and sub['prob_id'] == pid and sub['status'] not in ('OK', 'AC'))
                if wa_attempts > 0: prob_info['display'] = '-' + str(wa_attempts)
        
        team['solved'] = current_solved
        team['penalty'] = current_penalty

    # 根据解题数和罚时对榜单进行排序
    current_board.sort(key=lambda x: (-x['solved'], x['penalty']))
    rank, last_solved, last_penalty = 0, -1, -1
    for i, team in enumerate(current_board):
        if team['solved'] != last_solved or team['penalty'] != last_penalty: rank = i + 1
        team['rank'] = rank
        last_solved, last_penalty = team['solved'], team['penalty']

    # 计算并格式化题目统计信息
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
    """
    从 `contest.dat` 文件加载所有比赛数据到全局 CONTEST_STATE 变量中。
    这是应用启动时必须执行的关键初始化步骤。
    """
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

# 应用启动时立即加载数据
load_initial_data()

@app.route('/')
def scoreboard_page():
    """渲染主榜单回放页面。"""
    return render_template('index.html')

@app.route('/api/initial_data')
def api_initial_data():
    """
    提供给前端的API接口，返回比赛的基本信息。
    包括题目列表和比赛总时长（秒）。
    """
    return jsonify({
        'problems': CONTEST_STATE["problem_ids"], 
        'total_duration_sec': 300 * 60 # 比赛总时长硬编码为 300 分钟
    })

@app.route('/api/board_at_time/<int:seconds>')
def api_board_at_time(seconds):
    """
    提供给前端的API接口，返回指定时间点的榜单和统计数据。
    """
    board_data, stats_data = calculate_board_at_time(seconds)
    return jsonify({'board': board_data, 'statistics': stats_data})

@app.route('/update', methods=['GET', 'POST'])
def update_submission():
    """
    处理后台控制面板的逻辑。
    - GET请求: 显示表单页面，用于添加提交或队伍。
    - POST请求: 处理表单提交，将新的提交记录注入系统并刷新全局状态。
    """
    if request.method == 'POST':
        # 从表单中提取新提交的数据
        session['selected_team_id'] = int(request.form['team_id']) # 记录当前选择的队伍，方便刷新后保持选中
        prob_id = request.form['problem_id']
        result = request.form['result']
        new_submission = { 'team_id': int(request.form['team_id']), 'prob_id': prob_id, 'status': 'AC' if result == 'AC' else 'WA' }
        
        # 根据提交结果（AC/WA）计算提交时间（秒）
        if result == 'AC':
            try: solved_time_min = int(request.form.get('solved_time_min', 0))
            except (ValueError, TypeError): solved_time_min = 0
            new_submission['time'] = solved_time_min * 60
        else:
            try: wa_time_min = int(request.form.get('solved_time_min', 1)) - 1
            except (ValueError, TypeError): wa_time_min = 0
            new_submission['time'] = wa_time_min * 60

        # 将新提交添加到全局列表并重新排序
        CONTEST_STATE["all_submissions"].append(new_submission)
        CONTEST_STATE["all_submissions"].sort(key=lambda x: x['time'])
        print(f"新提交已注入: {new_submission}")
        
        # 基于更新后的提交列表，重新计算整个比赛的最终榜单状态
        _, new_initial_board = calculate_final_board_state(
            CONTEST_STATE["teams_map"],
            CONTEST_STATE["problems_info"],
            CONTEST_STATE["all_submissions"]
        )
        CONTEST_STATE["initial_board"] = new_initial_board
        print("全局最终状态已刷新！")
        
        return redirect(url_for('update_submission'))
    
    # 对于GET请求，渲染更新页面
    selected_team_id = session.pop('selected_team_id', None)
    return render_template('update.html', 
                           teams=CONTEST_STATE["initial_board"], 
                           problems=CONTEST_STATE["problem_ids"],
                           selected_team_id=selected_team_id)

@app.route('/add_team', methods=['POST'])
def add_team():
    """
    处理添加新队伍的POST请求。
    """
    new_team_name = request.form.get('team_name')
    if new_team_name:
        # 确定新队伍的ID
        max_id = max(CONTEST_STATE["teams_map"].keys()) if CONTEST_STATE["teams_map"] else 0
        new_id = max_id + 1
        # 将新队伍添加到队伍映射中
        CONTEST_STATE["teams_map"][new_id] = {'id': new_id, 'school': 'N/A', 'name': new_team_name}

        # 添加队伍后，需要重新计算榜单以包含这个新队伍
        _, new_initial_board = calculate_final_board_state(
            CONTEST_STATE["teams_map"],
            CONTEST_STATE["problems_info"],
            CONTEST_STATE["all_submissions"]
        )
        CONTEST_STATE["initial_board"] = new_initial_board
        print(f"新队伍已添加并刷新榜单: {new_team_name}")

    return redirect(url_for('update_submission'))

# 当脚本作为主程序运行时，启动 Flask 开发服务器
if __name__ == '__main__':
    app.run(port=5000) # 指定在5000端口上运行应用