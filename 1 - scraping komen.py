import requests
import re
import time
import pandas as pd
from datetime import datetime

def get_tiktok_video_id(link):
    """
    Get TikTok video ID from any TikTok link (short or long)
    """
    try:
        # Follow redirect untuk link pendek
        response = requests.get(link, allow_redirects=True, timeout=10)
        final_url = response.url
        
        # Ekstrak ID dari URL final
        match = re.search(r'video/(\d+)', final_url)
        if match:
            return match.group(1)
        
        # Alternatif: cari di content response
        content = response.text
        match = re.search(r'"id":"(\d+)"', content)
        if match:
            return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"Error saat konversi link: {e}")
        return None

def scrape_tiktok_comments(aweme_id, total_comments, include_replies=True):
    """
    Scrape komentar TikTok berdasarkan aweme_id
    
    Args:
        aweme_id: ID video TikTok
        total_comments: Jumlah total komentar yang ingin diambil
        include_replies: Apakah termasuk reply atau hanya komentar utama
    """
    base_url = "https://www.tiktok.com/api/comment/list/"
    all_data = []
    cursor = 0
    count = min(total_comments, 50)
    main_comment_count = 0
    
    print(f"Mulai scraping untuk video ID: {aweme_id}")
    print(f"Mode: {'Komentar + Reply' if include_replies else 'Hanya komentar utama'}")
    print(f"Target total: {total_comments} item\n")
    
    while len(all_data) < total_comments:
        params = {
            'aid': '1988',
            'aweme_id': aweme_id,
            'count': count,
            'cursor': cursor
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'comments' not in data or not data['comments']:
                print("Tidak ada komentar lagi.")
                break
            
            for comment in data['comments']:
                if len(all_data) >= total_comments:
                    break
                
                username = comment['user']['unique_id'] or comment['user']['nickname']
                text = comment['text']
                comment_id = comment['cid']
                reply_count = comment.get('reply_comment_total', 0)
                main_comment_count += 1
                
                all_data.append({
                    'username': username,
                    'text': text,
                    'type': 'main'
                })
                print(f"[MAIN #{main_comment_count}] @{username}: {text[:50]}...")
                
                if include_replies and reply_count > 0:
                    print(f"  → Mengambil {reply_count} reply...")
                    replies = scrape_tiktok_replies(aweme_id, comment_id, reply_count)
                    for reply in replies:
                        if len(all_data) >= total_comments:
                            break
                        all_data.append(reply)
                        print(f"     [REPLY] @{reply['username']}: {reply['text'][:50]}...")
            
            cursor = data.get('cursor', 0)
            if not data.get('has_more', 0):
                print("Sudah mencapai akhir komentar.")
                break
            
            time.sleep(0.5)
            
        except requests.exceptions.RequestException as e:
            print(f"Error saat request: {e}")
            break
        except KeyError as e:
            print(f"Error parsing data: {e}")
            break
    
    return all_data

def scrape_tiktok_replies(aweme_id, comment_id, total_replies):
    """Scrape reply dari sebuah komentar"""
    replies_url = "https://www.tiktok.com/api/comment/list/reply/"
    all_replies = []
    cursor = 0
    count = min(total_replies, 50)
    
    while len(all_replies) < total_replies:
        params = {
            'aid': '1988',
            'comment_id': comment_id,
            'item_id': aweme_id,
            'count': count,
            'cursor': cursor
        }
        
        try:
            response = requests.get(replies_url, params=params)
            
            if response.status_code != 200:
                print(f"    ⚠️ Gagal mengambil reply (status {response.status_code})")
                break
            
            data = response.json()
            replies_batch = data.get('comments', data.get('replies', []))
            
            if not replies_batch:
                break
            
            for reply in replies_batch:
                if len(all_replies) >= total_replies:
                    break
                
                username = reply['user']['unique_id'] or reply['user']['nickname']
                text = reply['text']
                
                all_replies.append({
                    'username': username,
                    'text': text,
                    'type': 'reply'
                })
            
            cursor = data.get('cursor', 0)
            if not data.get('has_more', 0):
                break
                
            time.sleep(0.3)
            
        except Exception as e:
            print(f"    ⚠️ Error ambil reply: {e}")
            break
    
    return all_replies

def save_to_excel(data, filename):
    """Menyimpan data ke file Excel"""
    df = pd.DataFrame(data)
    df = df[['text', 'username', 'type']]
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='TikTok Comments', index=False)
        
        worksheet = writer.sheets['TikTok Comments']
        worksheet.column_dimensions['A'].width = 50
        worksheet.column_dimensions['B'].width = 20
        worksheet.column_dimensions['C'].width = 12
    
    print(f"\n✓ Data berhasil disimpan ke {filename}")
    print(f"  Total {len(data)} baris data")
    print(f"  - Komentar utama: {sum(1 for d in data if d['type'] == 'main')} baris")
    print(f"  - Reply: {sum(1 for d in data if d['type'] == 'reply')} baris")

def main():
    print("="*60)
    print("SCRAPER KOMENTAR TIKTOK DENGAN REPLY")
    print("="*60)
    print()
    
    # Input link atau ID video
    user_input = input("Masukkan link TikTok atau ID video: ").strip()
    
    if not user_input:
        print("Input tidak boleh kosong!")
        return
    
    # Cek apakah input adalah link atau ID
    if 'tiktok.com' in user_input or 'vt.tiktok.com' in user_input:
        print("\n🔗 Mendeteksi link TikTok, mengkonversi ke ID video...")
        aweme_id = get_tiktok_video_id(user_input)
        
        if aweme_id:
            print(f"✓ Berhasil! ID Video: {aweme_id}")
        else:
            print("❌ Gagal mengkonversi link ke ID video!")
            return
    else:
        # Input langsung berupa ID video (numeric)
        if user_input.isdigit():
            aweme_id = user_input
            print(f"✓ Menggunakan ID video: {aweme_id}")
        else:
            print("❌ Input tidak valid! Masukkan link TikTok atau ID video numeric.")
            return
    
    # Input jumlah komentar
    print("\n" + "-"*60)
    while True:
        try:
            total_comments = int(input("Masukkan jumlah total item yang ingin diambil: ").strip())
            if total_comments > 0:
                break
            else:
                print("Jumlah harus lebih dari 0!")
        except ValueError:
            print("Masukkan angka yang valid!")
    
    # Pilihan mode scraping
    print("\nPilih mode scraping:")
    print("1. Hanya komentar utama (tanpa reply)")
    print("2. Komentar utama beserta reply")
    
    while True:
        mode = input("Pilihan (1/2): ").strip()
        if mode in ['1', '2']:
            include_replies = (mode == '2')
            break
        else:
            print("Pilihan tidak valid! Masukkan 1 atau 2.")
    
    print("\n" + "="*60)
    print("MEMULAI SCRAPING...")
    print("="*60 + "\n")
    
    # Scrape komentar
    comments_data = scrape_tiktok_comments(aweme_id, total_comments, include_replies)
    
    if not comments_data:
        print("\nTidak ada data yang berhasil diambil!")
        return
    
    # Tampilkan statistik
    print("\n" + "="*60)
    print("HASIL SCRAPING")
    print("="*60)
    print(f"Total data terkumpul: {len(comments_data)} item")
    print(f"- Komentar utama: {sum(1 for d in comments_data if d['type'] == 'main')}")
    print(f"- Reply: {sum(1 for d in comments_data if d['type'] == 'reply')}")
    
    # Preview 5 data pertama
    print("\nPREVIEW 5 DATA PERTAMA:")
    print("-"*60)
    for i, item in enumerate(comments_data[:5], 1):
        print(f"{i}. [{item['type'].upper()}] @{item['username']}")
        print(f"   Text: {item['text'][:100]}...")
        print()
    
    # Tanya apakah mau simpan ke Excel
    save_option = input("\nSimpan ke file Excel? (y/n): ").strip().lower()
    if save_option == 'y':
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tiktok_comments_{aweme_id}_{timestamp}.xlsx"
        
        save_to_excel(comments_data, filename)
        
        print("\n✓ Proses selesai!")
    else:
        print("\nData tidak disimpan. Terima kasih!")

if __name__ == "__main__":
    # Cek apakah library yang diperlukan terinstall
    try:
        import pandas
        import openpyxl
    except ImportError as e:
        print("ERROR: Library diperlukan tidak terinstall!")
        print("Silakan install dengan perintah:")
        print("pip install pandas openpyxl requests")
        exit(1)
    
    main()