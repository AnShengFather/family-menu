#!/usr/bin/env python3
"""初始化数据库，添加示例菜品"""

import sys
import os

# 确保能找到 app.py 中的模型
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, db, Dish

SAMPLE_DISHES = [
    # 荤菜
    {"name": "红烧肉", "category": "荤菜", "price": 28, "description": "入口即化"},
    {"name": "可乐鸡翅", "category": "荤菜", "price": 22, "description": "小朋友最爱"},
    {"name": "鱼香肉丝", "category": "荤菜", "price": 20, "description": "酸甜下饭"},
    {"name": "宫保鸡丁", "category": "荤菜", "price": 22, "description": "花生脆，鸡肉嫩"},
    {"name": "回锅肉", "category": "荤菜", "price": 24, "description": "蒜苗炒香"},
    {"name": "麻婆豆腐", "category": "荤菜", "price": 16, "description": "微辣麻香"},
    {"name": "番茄牛腩", "category": "荤菜", "price": 32, "description": "汤浓肉烂"},
    {"name": "青椒肉丝", "category": "荤菜", "price": 18, "description": ""},
    {"name": "蒜苔炒肉", "category": "荤菜", "price": 18, "description": ""},
    {"name": "土豆烧排骨", "category": "荤菜", "price": 28, "description": ""},

    # 素菜
    {"name": "蒜蓉西蓝花", "category": "素菜", "price": 14, "description": ""},
    {"name": "手撕包菜", "category": "素菜", "price": 12, "description": "酸辣脆爽"},
    {"name": "地三鲜", "category": "素菜", "price": 16, "description": "茄子土豆青椒"},
    {"name": "酸辣土豆丝", "category": "素菜", "price": 10, "description": ""},
    {"name": "蚝油生菜", "category": "素菜", "price": 10, "description": "5分钟搞定"},
    {"name": "干煸四季豆", "category": "素菜", "price": 14, "description": ""},
    {"name": "葱烧豆腐", "category": "素菜", "price": 12, "description": ""},
    {"name": "西葫芦炒蛋", "category": "素菜", "price": 12, "description": ""},
    {"name": "韭菜炒鸡蛋", "category": "素菜", "price": 12, "description": ""},
    {"name": "豆豉鲮鱼油麦菜", "category": "素菜", "price": 14, "description": ""},
    {"name": "荷兰豆炒腊肠", "category": "素菜", "price": 16, "description": ""},

    # 汤
    {"name": "西红柿蛋汤", "category": "汤", "price": 8, "description": ""},
    {"name": "紫菜蛋花汤", "category": "汤", "price": 6, "description": ""},
    {"name": "冬瓜排骨汤", "category": "汤", "price": 18, "description": "清淡鲜甜"},
    {"name": "玉米排骨汤", "category": "汤", "price": 20, "description": "清甜好喝"},

    # 主食
    {"name": "白米饭", "category": "主食", "price": 2, "description": ""},
    {"name": "蛋炒饭", "category": "主食", "price": 8, "description": ""},
    {"name": "炒面", "category": "主食", "price": 10, "description": ""},

    # 凉菜
    {"name": "拍黄瓜", "category": "凉菜", "price": 8, "description": "蒜香酸爽"},
    {"name": "凉拌木耳", "category": "凉菜", "price": 10, "description": ""},
    {"name": "皮蛋豆腐", "category": "凉菜", "price": 10, "description": ""},
]

def init():
    with app.app_context():
        db.create_all()
        # 检查是否已有数据
        if Dish.query.first():
            print("⚠️  数据库已有菜品，跳过初始化。如需重置请先删除 menu.db")
            return
        for data in SAMPLE_DISHES:
            dish = Dish(**data)
            db.session.add(dish)
        db.session.commit()
        print(f"✅ 已添加 {len(SAMPLE_DISHES)} 道示例菜品")

if __name__ == "__main__":
    init()
