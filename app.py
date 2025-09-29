# app.py

from flask import Flask, render_template, request, redirect, url_for, jsonify
from data_parser import parse_contest_data
import copy
import datetime  # <--- 1. 引入datetime模块

app = Flask(__name__)

# --- 全局状态变量 ---
CONTEST_STATE = {
    "problem_ids": [],
    "board_data": [],
    "original_data": [],
    "contest_start_time": None, # <--- 2. 新增比赛开始时间
    "submissions_per_problem": {},  # 新增
    "statistics": {}  # 新增
}


# --- 【全新】统计计算函数 ---
def calculate_statistics():
    """【已重构】根据当前榜单状态计算详细的题目统计数据"""
    problem_ids = CONTEST_STATE["problem_ids"]
    board_data = CONTEST_STATE["board_data"]
    submissions_per_problem = CONTEST_STATE["submissions_per_problem"]

    if not board_data or not problem_ids:
        return {}

    stats = {
        'Submitted': {pid: 0 for pid in problem_ids},
        'Attempted': {pid: 0 for pid in problem_ids},  # 至少提交过一次的队伍数
        'Accepted': {pid: 0 for pid in problem_ids},  # AC的队伍数
        'Dirt': {pid: 0 for pid in problem_ids},  # WA后AC的队伍数
        'First Solved': {pid: float('inf') for pid in problem_ids},
        'Last Solved': {pid: float('-inf') for pid in problem_ids}
    }

    # 1. 填充 Submitted
    for pid, count in submissions_per_problem.items():
        if pid in stats['Submitted']:
            stats['Submitted'][pid] = count

    # 2. 遍历榜单计算 Attempted, Accepted, Dirt, Solved Times
    for team in board_data:
        for pid in problem_ids:
            prob_info = team['status'].get(pid)
            if not prob_info: continue

            is_ac = '+' in prob_info['display']
            is_wa = '-' in prob_info['display']

            # 只要有过提交记录（AC或WA），就计入 Attempted
            if is_ac or is_wa:
                stats['Attempted'][pid] += 1

            if is_ac:
                stats['Accepted'][pid] += 1

                # 如果不是一次AC，就计入Dirt
                if prob_info['display'] != '+':
                    stats['Dirt'][pid] += 1

                solved_time = prob_info.get('solved_time', 0)
                if solved_time < stats['First Solved'][pid]:
                    stats['First Solved'][pid] = solved_time
                if solved_time > stats['Last Solved'][pid]:
                    stats['Last Solved'][pid] = solved_time

    # 3. 格式化最终输出，使用正确的百分比计算逻辑
    formatted_stats = {}
    row_order = ['Submitted', 'Attempted', 'Accepted', 'Dirt', 'SE', 'First Solved', 'Last Solved']
    for row_name in row_order:
        formatted_stats[row_name] = {}
        for pid in problem_ids:
            if row_name == 'Submitted':
                formatted_stats[row_name][pid] = str(stats['Submitted'][pid])

            elif row_name == 'Attempted':
                count = stats['Attempted'][pid]
                total_submissions = stats['Submitted'].get(pid, 1)  # 防止除零
                percent = f"({count / total_submissions * 100:.0f}%)" if total_submissions > 0 else "(0%)"
                formatted_stats[row_name][pid] = f"{count}<br><small>{percent}</small>"

            elif row_name == 'Accepted':
                count = stats['Accepted'][pid]
                total_submissions = stats['Submitted'].get(pid, 1)
                percent = f"({count / total_submissions * 100:.0f}%)" if total_submissions > 0 else "(0%)"
                formatted_stats[row_name][pid] = f"{count}<br><small>{percent}</small>"

            elif row_name == 'Dirt':
                count = stats['Dirt'][pid]
                attempted_teams = stats['Attempted'].get(pid, 1)
                percent = f"({count / attempted_teams * 100:.0f}%)" if attempted_teams > 0 else "(NaN)"
                formatted_stats[row_name][pid] = f"{count}<br><small>{percent}</small>"

            elif row_name == 'SE':  # Solution Efficiency (这个指标似乎没有标准定义，这里保留 Accepted/Attempted)
                accepted_teams = stats['Accepted'][pid]
                attempted_teams = stats['Attempted'][pid]
                se_val = f"{accepted_teams / attempted_teams:.2f}" if attempted_teams > 0 else "0.00"
                formatted_stats[row_name][pid] = se_val

            elif row_name in ['First Solved', 'Last Solved']:
                time_val = stats[row_name][pid]
                formatted_stats[row_name][pid] = str(time_val) if time_val != float('inf') and time_val != float(
                    '-inf') else "Null"

    return formatted_stats


# --- 后台逻辑函数 ---
def load_and_initialize_board():
    """从文件加载并初始化比赛状态"""
    try:
        problem_ids, board_data, submissions_per_problem = parse_contest_data('contest.dat')
        CONTEST_STATE["problem_ids"] = problem_ids
        CONTEST_STATE["board_data"] = board_data
        CONTEST_STATE["original_data"] = copy.deepcopy(board_data)
        # 记录比赛“模拟”开始的时间
        CONTEST_STATE["contest_start_time"] = datetime.datetime.now()  # <--- 3. 记录启动时间
        CONTEST_STATE["submissions_per_problem"] = submissions_per_problem # 存储新数据
        recalculate_board()  # 首次加载后计算一次
        print("比赛数据加载成功！")
    except FileNotFoundError:
        print("错误：contest.dat 文件未找到！")


# ... recalculate_board() 函数保持不变 ...
def recalculate_board():
    for team in CONTEST_STATE["board_data"]:
        solved_count = 0
        total_penalty = 0
        for pid, prob_info in team['status'].items():
            if '+' in prob_info['display']:
                solved_count += 1
                total_penalty += prob_info['penalty']
        team['solved'] = solved_count
        team['penalty'] = total_penalty
    CONTEST_STATE["board_data"].sort(key=lambda x: (-x['solved'], x['penalty']))
    CONTEST_STATE["statistics"] = calculate_statistics()
    rank = 0
    last_solved = -1
    last_penalty = -1
    for i, team in enumerate(CONTEST_STATE["board_data"]):
        if team['solved'] != last_solved or team['penalty'] != last_penalty:
            rank = i + 1
        team['rank'] = rank
        last_solved = team['solved']
        last_penalty = team['penalty']


# --- 在程序启动时，Flask加载此文件时，就立即执行数据加载 ---
load_and_initialize_board()


# ... @app.route('/') 和 @app.route('/api/board') 保持不变 ...
@app.route('/')
def scoreboard():
    return render_template('index.html')


@app.route('/api/board')
def api_board_data():
    return jsonify({
        'problems': CONTEST_STATE["problem_ids"],
        'board': CONTEST_STATE["board_data"],
        'statistics': CONTEST_STATE["statistics"]
    })


@app.route('/update', methods=['GET', 'POST'])
def update_submission():
    """【已重构】用于显示和处理更新提交的表单"""
    if request.method == 'POST':
        team_id_to_update = int(request.form['team_id'])
        prob_id = request.form['problem_id']
        result = request.form['result']

        team_to_update = None
        for team in CONTEST_STATE["board_data"]:
            if team['team_id'] == team_id_to_update:
                team_to_update = team
                break

        if team_to_update and prob_id in team_to_update['status']:
            prob_status = team_to_update['status'][prob_id]

            if result == 'AC':
                if '+' not in prob_status['display']:
                    # --- 【核心修改】从表单获取时间，而不是用datetime ---
                    # request.form.get() 更安全，可以设置默认值
                    try:
                        solved_time_min = int(request.form.get('solved_time_min', 0))
                    except (ValueError, TypeError):
                        solved_time_min = 0  # 如果转换失败，给个默认值

                    prob_status['solved_time'] = solved_time_min
                    penalty_per_wa = 20

                    attempts = int(prob_status['display'].replace('-', '')) if prob_status['display'] else 0
                    prob_status['display'] = '+' + (str(attempts) if attempts > 0 else '')

                    # 使用你输入的时间来计算罚时
                    prob_status['penalty'] = solved_time_min + attempts * penalty_per_wa
            else:  # WA
                if '+' not in prob_status['display']:
                    attempts = int(prob_status['display'].replace('-', '')) if prob_status['display'] else 0
                    prob_status['display'] = '-' + str(attempts + 1)

        recalculate_board()
        return redirect(url_for('update_submission'))

    return render_template('update.html', teams=CONTEST_STATE["board_data"], problems=CONTEST_STATE["problem_ids"])

# --- 6. 【功能新增】添加新队伍的路由 ---
@app.route('/add_team', methods=['POST'])
def add_team():
    """用于从表单添加一个新队伍"""
    new_team_name = request.form.get('team_name')
    if new_team_name:
        # 找到当前最大的 team_id, 以免冲突
        max_id = 0
        for team in CONTEST_STATE["board_data"]:
            if team['team_id'] > max_id:
                max_id = team['team_id']

        # 创建新队伍对象
        new_team = {
            'team_id': max_id + 1,
            'rank': 999,  # 临时排名
            'team': new_team_name,
            'solved': 0,
            'penalty': 0,
            'status': {pid: {'display': '', 'penalty': 0, 'solved_time': 0} for pid in CONTEST_STATE["problem_ids"]}
        }
        CONTEST_STATE["board_data"].append(new_team)
        recalculate_board()  # 重新计算排名

    return redirect(url_for('update_submission'))


# ... @app.route('/reset') 保持不变 ...
@app.route('/reset')
def reset_board():
    CONTEST_STATE["board_data"] = copy.deepcopy(CONTEST_STATE["original_data"])
    recalculate_board()
    return redirect(url_for('scoreboard'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)