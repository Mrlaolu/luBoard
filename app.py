from flask import Flask, render_template
from data_parser import parse_contest_data # 导入我们刚写的函数

app = Flask(__name__)

@app.route('/')
def scoreboard():
    # 调用解析函数，它会返回题目ID列表和处理好的榜单数据
    try:
        # 假设 contest.dat 文件和 app.py 在同一个目录下
        problem_ids, board_data = parse_contest_data('contest.dat')
    except FileNotFoundError:
        # 如果文件不存在，提供一个错误提示或空数据
        problem_ids = []
        board_data = []
        # 你也可以在这里渲染一个专门的错误页面
        return "错误：contest.dat 文件未找到！", 404

    return render_template('index.html', problems=problem_ids, board=board_data)

if __name__ == '__main__':
    app.run(debug=True)