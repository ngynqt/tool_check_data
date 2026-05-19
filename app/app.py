from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import os
import json
from werkzeug.utils import secure_filename
""" 

"""

app = Flask(__name__, static_folder='static')
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global dataset storage
datasets = {}

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'xlsm', 'xlsb'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_file(path):
    ext = path.lower().split('.')[-1]
    if ext in ('xls', 'xlsx', 'xlsm', 'xlsb'):
        return pd.read_excel(path, engine='openpyxl')
    else:
        try:
            return pd.read_csv(path, encoding='utf-8')
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding='latin1')

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Upload one or multiple files and merge into dataset"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400

    dfs = []
    file_names = []
    errors = []

    for f in files:
        if f and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            f.save(filepath)
            try:
                df = load_file(filepath)
                dfs.append(df)
                file_names.append(filename)
            except Exception as e:
                errors.append(f'Lỗi đọc {filename}: {str(e)}')
        else:
            errors.append(f'File không hợp lệ: {f.filename}')

    if not dfs:
        return jsonify({'error': 'Không đọc được file nào', 'details': errors}), 400

    dataset = pd.concat(dfs, ignore_index=True)
    datasets['main'] = dataset.copy()
    datasets['original'] = dataset.copy()

    # Basic info
    info = {
        'files': file_names,
        'rows': len(dataset),
        'cols': len(dataset.columns),
        'columns': list(dataset.columns),
        'errors': errors,
        'head': dataset.head(10).to_dict(orient='records'),
        'null_counts': dataset.isnull().sum().to_dict(),
        'dtypes': {col: str(dtype) for col, dtype in dataset.dtypes.items()}
    }

    return jsonify({'success': True, 'info': info})

@app.route('/api/visualize_null_all', methods=['POST'])
def visualize_null_all():
    """Visualize null values for ALL columns"""
    if 'main' not in datasets:
        return jsonify({'error': 'Chưa có dataset. Hãy upload file trước.'}), 400

    dataset = datasets['main']
    null_counts = dataset.isnull().sum()

    fig, ax = plt.subplots(figsize=(max(10, len(dataset.columns) * 0.8), 6))
    colors = ['#ef4444' if v > 0 else '#22c55e' for v in null_counts.values]
    bars = ax.bar(null_counts.index, null_counts.values, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_title('Số lượng giá trị Null trong mỗi cột', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Cột', fontsize=11)
    ax.set_ylabel('Số lượng Null', fontsize=11)
    plt.xticks(rotation=45, ha='right', fontsize=9)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    for bar, val in zip(bars, null_counts.values):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                   str(val), ha='center', va='bottom', fontsize=8, fontweight='bold')
    fig.patch.set_facecolor('#1e293b')
    ax.set_facecolor('#0f172a')
    ax.tick_params(colors='#94a3b8')
    ax.xaxis.label.set_color('#94a3b8')
    ax.yaxis.label.set_color('#94a3b8')
    ax.title.set_color('#f1f5f9')
    for spine in ax.spines.values():
        spine.set_edgecolor('#334155')
    plt.tight_layout()

    img = fig_to_base64(fig)
    return jsonify({'success': True, 'image': img, 'null_counts': null_counts.to_dict()})

@app.route('/api/check_null_key_cols', methods=['POST'])
def check_null_key_cols():
    """Check null values in key columns: SĐT, Facebook, SĐT 2"""
    if 'main' not in datasets:
        return jsonify({'error': 'Chưa có dataset.'}), 400

    dataset = datasets['main']
    key_cols = ['SĐT', 'Facebook', 'SĐT 2']
    available_cols = [c for c in key_cols if c in dataset.columns]

    if not available_cols:
        return jsonify({'error': f'Không tìm thấy các cột {key_cols} trong dataset.'}), 400

    null_counts = dataset[available_cols].isnull().sum()

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ['#ef4444' if v > 0 else '#22c55e' for v in null_counts.values]
    bars = ax.bar(null_counts.index, null_counts.values, color=colors, width=0.5, edgecolor='white')
    ax.set_title('Null Values - Cột quan trọng (SĐT, Facebook, SĐT 2)', fontsize=13, fontweight='bold', pad=15)
    ax.set_xlabel('Cột', fontsize=11)
    ax.set_ylabel('Số lượng Null', fontsize=11)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    for bar, val in zip(bars, null_counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(null_counts.values)*0.01,
               str(val), ha='center', va='bottom', fontsize=11, fontweight='bold',
               color='white')
    fig.patch.set_facecolor('#1e293b')
    ax.set_facecolor('#0f172a')
    ax.tick_params(colors='#94a3b8')
    ax.xaxis.label.set_color('#94a3b8')
    ax.yaxis.label.set_color('#94a3b8')
    ax.title.set_color('#f1f5f9')
    for spine in ax.spines.values():
        spine.set_edgecolor('#334155')
    plt.tight_layout()

    img = fig_to_base64(fig)
    return jsonify({
        'success': True,
        'image': img,
        'null_counts': null_counts.to_dict(),
        'total_rows': len(dataset)
    })

@app.route('/api/evaluate_null', methods=['POST'])
def evaluate_null():
    """Remove rows where SĐT, Facebook, AND SĐT 2 are all null"""
    if 'main' not in datasets:
        return jsonify({'error': 'Chưa có dataset.'}), 400

    dataset = datasets['main']
    key_cols = ['SĐT', 'Facebook', 'SĐT 2']
    available_cols = [c for c in key_cols if c in dataset.columns]

    before = len(dataset)
    if available_cols:
        null_counts = dataset[available_cols].isnull().sum(axis=1)
        dataset_cleaned = dataset[null_counts < len(available_cols)].copy()
    else:
        dataset_cleaned = dataset.copy()

    datasets['main'] = dataset_cleaned
    after = len(dataset_cleaned)

    return jsonify({
        'success': True,
        'before': before,
        'after': after,
        'removed': before - after,
        'message': f'Đã xóa {before - after} dòng có null ở tất cả cột ({", ".join(available_cols)})'
    })

@app.route('/api/dataset_info', methods=['GET'])
def dataset_info():
    """Get current dataset info"""
    if 'main' not in datasets:
        return jsonify({'loaded': False})

    dataset = datasets['main']
    return jsonify({
        'loaded': True,
        'rows': len(dataset),
        'cols': len(dataset.columns),
        'columns': list(dataset.columns),
        'null_counts': dataset.isnull().sum().to_dict(),
        'head': dataset.head(20).fillna('').to_dict(orient='records')
    })

@app.route('/api/reset', methods=['POST'])
def reset_dataset():
    """Reset dataset to original uploaded data"""
    if 'original' not in datasets:
        return jsonify({'error': 'Không có dataset gốc.'}), 400

    datasets['main'] = datasets['original'].copy()
    return jsonify({'success': True, 'rows': len(datasets['main'])})

@app.route('/api/data_summary', methods=['GET'])
def data_summary():
    """Get statistical summary"""
    if 'main' not in datasets:
        return jsonify({'error': 'Chưa có dataset.'}), 400

    dataset = datasets['main']
    summary = {}
    for col in dataset.columns:
        col_data = dataset[col]
        summary[col] = {
            'non_null': int(col_data.notna().sum()),
            'null': int(col_data.isna().sum()),
            'null_pct': round(col_data.isna().sum() / len(dataset) * 100, 1),
            'dtype': str(col_data.dtype),
            'unique': int(col_data.nunique())
        }
    return jsonify({'success': True, 'summary': summary, 'total_rows': len(dataset)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
