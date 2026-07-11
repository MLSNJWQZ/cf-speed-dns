#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 更新器 支持自动新建解析
"""

import json
import traceback
import time
import os
import requests

# API 配置
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}
DEFAULT_TIMEOUT = 30

def get_cf_speed_test_ip(timeout=10, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.get(
                'https://ip.164746.xyz/ipTop.html',
                timeout=timeout
            )
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"获取优选 IP 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
    return None

def get_dns_records(name):
    records = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            result = response.json().get('result', [])
            for record in result:
                if record.get('name') == name and record.get('type') == 'A':
                    records.append({
                        'id': record['id'],
                        'content': record.get('content', '')
                    })
        else:
            print(f'获取 DNS 记录失败: {response.text}')
    except Exception as e:
        print(f'获取 DNS 记录异常: {e}')
        traceback.print_exc()
    return records

def create_dns_record(name, ip):
    """新增DNS解析记录"""
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    data = {
        "type": "A",
        "name": name,
        "content": ip,
        "ttl": 300,
        "proxied": False
    }
    try:
        res = requests.post(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        if res.json()["success"]:
            print(f"✅ 成功新建解析 {name} → {ip}")
            return f"新建解析：{name} → {ip}"
        else:
            print(f"❌ 新建失败：{res.text}")
            return f"新建解析失败：{res.text}"
    except Exception as e:
        traceback.print_exc()
        return f"新建解析异常：{e}"

def update_dns_record(record_info, name, cf_ip):
    record_id = record_info['id']
    current_ip = record_info.get('content', '')
    if current_ip == cf_ip:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"cf_dns_change skip: ---- Time: {current_time} ---- ip：{cf_ip} (已是最新)")
        return f"ip:{cf_ip} 解析 {name} 跳过 (已是最新)"

    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        "ttl": 300,
        "proxied": False
    }
    try:
        response = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        if response.status_code == 200:
            print(f"cf_dns_change success: ---- Time: {current_time} ---- ip：{cf_ip}")
            return f"ip:{cf_ip} 解析 {name} 更新成功"
        else:
            print(f"cf_dns_change ERROR: ---- Time: {current_time} ---- MESSAGE: {response.text}")
            return f"ip:{cf_ip} 解析 {name} 更新失败"
    except Exception as e:
        traceback.print_exc()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"cf_dns_change ERROR: ---- Time: {current_time} ---- MESSAGE: {e}")
        return f"ip:{cf_ip} 解析 {name} 更新异常"

def push_plus(content):
    if not PUSHPLUS_TOKEN:
        print("PUSHPLUS_TOKEN 未设置，跳过消息推送")
        return
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "IP优选DNSCF推送",
        "content": content,
        "template": "markdown",
        "channel": "wechat"
    }
    try:
        body = json.dumps(data).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        requests.post(url, data=body, headers=headers, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        print(f"消息推送失败: {e}")

def main():
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("错误: 缺少必要的环境变量 (CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME)")
        return

    ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        print("错误: 无法获取优选 IP")
        return

    ip_addresses = [ip.strip() for ip in ip_addresses_str.split(',') if ip.strip()]
    if not ip_addresses:
        print("错误: 未解析到有效 IP 地址")
        return

    dns_records = get_dns_records(CF_DNS_NAME)
    push_plus_content = []

    # 没有记录就直接新建第一条IP
    if not dns_records:
        msg = create_dns_record(CF_DNS_NAME, ip_addresses[0])
        push_plus_content.append(msg)
    else:
        if len(ip_addresses) > len(dns_records):
            print(f"警告: IP 数量({len(ip_addresses)})超过 DNS 记录数量({len(dns_records)})，只更新前 {len(dns_records)} 个")
            ip_addresses = ip_addresses[:len(dns_records)]
        for index, ip_address in enumerate(ip_addresses):
            dns = update_dns_record(dns_records[index], CF_DNS_NAME, ip_address)
            push_plus_content.append(dns)

    if push_plus_content:
        push_plus('\n'.join(push_plus_content))

if __name__ == '__main__':
    main()
