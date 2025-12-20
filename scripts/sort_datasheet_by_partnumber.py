#!/usr/bin/env python3
"""
7400_series_ic_datasheet_collection_status.json ファイルの配列要素を
PartNumber の 74x 以下の番号順に並び替えるスクリプト
"""

import json
import re
import os


def extract_part_number(part_number):
    """
    PartNumber から数値部分を抽出して、ソート用のキーを生成
    例: "74x00" -> 0, "74x123" -> 123, "74x1000" -> 1000
    """
    match = re.search(r'74x(\d+)', part_number)
    if match:
        return int(match.group(1))
    return 0


def sort_datasheet_json():
    """
    データシート収集状況JSONファイルをPartNumber順に並び替え
    """
    # ファイルパス
    datasheet_file = "./datasheets/7400_series_ic_datasheet_collection_status.json"

    # JSONファイルを読み込み
    print(f"読み込み中: {datasheet_file}")
    with open(datasheet_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"読み込み完了: {len(data)} 個の要素")

    # PartNumber順にソート
    print("PartNumber順に並び替え中...")
    sorted_data = sorted(
        data, key=lambda x: extract_part_number(x['PartNumber']))

    # 並び替え前後の確認用ログ
    print("\n並び替え結果（最初の10個と最後の10個）:")
    print("最初の10個:")
    for i, item in enumerate(sorted_data[:10]):
        print(f"  {i+1}: {item['PartNumber']}")

    print("\n最後の10個:")
    for i, item in enumerate(sorted_data[-10:]):
        print(f"  {len(sorted_data)-9+i}: {item['PartNumber']}")

    # 重複チェック
    part_numbers = [item['PartNumber'] for item in sorted_data]
    duplicates = [pn for pn in set(part_numbers) if part_numbers.count(pn) > 1]
    if duplicates:
        print(f"\n警告: 重複するPartNumberが見つかりました: {duplicates}")

    # ソート済みデータを保存
    print(f"\n保存中: {datasheet_file}")
    with open(datasheet_file, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)

    print("並び替えが完了しました。")


if __name__ == "__main__":
    sort_datasheet_json()
