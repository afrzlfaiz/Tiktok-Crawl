import asyncio
from playwright.async_api import async_playwright
import json

async def search_tiktok(keyword: str, max_videos: int = 30):
    """Search TikTok dengan selector berdasarkan HTML real"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Jakarta",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
                "Referer": "https://www.google.com/",
                "DNT": "1"
            }
        )
        
        page = await context.new_page()

        search_url = f"https://www.tiktok.com/search?q={keyword.replace(' ', '%20')}"
        print(f"🔍 Membuka: {search_url}")

        await page.goto(search_url, wait_until="networkidle")
        await page.wait_for_timeout(5000)

        # Scroll method: monitor grid items until target reached
        print(f"📊 Memuat video (target: {max_videos} video)...")
        
        scroll_script = '''
            () => {
                const lastGrid = document.querySelector('[id^="grid-item-container-"]:last-child');
                if (lastGrid) {
                    lastGrid.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            }
        '''
        
        max_attempts = 50
        attempt = 0
        last_video_count = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            # Scroll ke bawah
            await page.evaluate(scroll_script)
            await page.wait_for_timeout(2000)
            
            # Hitung video yang sudah dimuat
            current_videos = await page.evaluate('''
                () => {
                    return document.querySelectorAll('a[href*="/video/"]').length;
                }
            ''')
            
            print(f"  📈 Attempt {attempt}: {current_videos} video ditemukan")
            
            # Stop jika sudah mencapai target atau tidak ada penambahan
            if current_videos >= max_videos:
                print(f"✅ Target {max_videos} video tercapai!")
                break
            
            if current_videos == last_video_count and attempt > 5:
                print(f"⚠️ Tidak ada penambahan video lagi (stop di {current_videos})")
                break
            
            last_video_count = current_videos

        # Ambil data dengan selector yang benar
        data = await page.evaluate('''
            () => {
                const videos = [];

                // Cari semua link video (berdasarkan struktur HTML yang diberikan)
                const videoLinks = document.querySelectorAll('a[href*="/video/"]');

                videoLinks.forEach((link, idx) => {
                    const videoUrl = link.href;
                    const videoId = videoUrl ? videoUrl.split('/video/')[1]?.split('?')[0] : null;

                    // Cari username dari href atau dari parent
                    let username = null;
                    const hrefParts = videoUrl?.split('/');
                    if (hrefParts && hrefParts.length > 3) {
                        username = hrefParts[3]?.replace('@', '');
                    }

                    // Cari container parent
                    const container = link.closest('[class*="DivWrapper"]') || link.parentElement;

                    // Cari caption dari alt attribute img
                    let caption = null;
                    const img = container?.querySelector('img');
                    if (img && img.alt) {
                        caption = img.alt;
                    }

                    if (videoId && username) {
                        videos.push({
                            no: idx + 1,
                            video_id: videoId,
                            url: videoUrl,
                            username: username,
                            caption: caption ? caption.substring(0, 200) : null
                        });
                    }
                });

                // Hapus duplikat berdasarkan video_id
                const unique = [];
                const seen = new Set();
                for (const video of videos) {
                    if (!seen.has(video.video_id)) {
                        seen.add(video.video_id);
                        unique.push(video);
                    }
                }

                return unique;
            }
        ''')

        await browser.close()
        return data

async def main():
    keyword = input("Masukkan keyword pencarian: ").strip()

    if not keyword:
        print("❌ Keyword tidak boleh kosong!")
        return
    
    try:
        max_videos = int(input("Masukkan jumlah video yang diinginkan: ").strip())
        if max_videos <= 0:
            print("❌ Jumlah video harus lebih dari 0!")
            return
    except ValueError:
        print("❌ Jumlah video harus berupa angka!")
        return

    print(f"\n🎯 Mencari: {keyword} (target: {max_videos} video)\n")
    results = await search_tiktok(keyword, max_videos)
    
    # Tampilkan hasil sesuai jumlah yang diminta
    display_count = min(len(results), max_videos)
    if results:
        print(f"\n✅ Ditemukan {len(results)} video, menampilkan {display_count}:\n")
        for video in results[:display_count]:
            print(f"{video['no']}. @{video['username']}")
            if video['caption']:
                caption_preview = video['caption'][:100] + "..." if len(video['caption']) > 100 else video['caption']
                print(f"   📝 {caption_preview}")
            print(f"   🔗 {video['url']}")
            print()
    else:
        print("❌ Tidak ada video ditemukan")
        print("\n💡 Tips: Coba buka browser manual dulu, mungkin kena challenge TikTok")
    
    # Simpan hasil
    with open(f"tiktok_{keyword.replace(' ', '_')}.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Data disimpan ke tiktok_{keyword.replace(' ', '_')}.json")

# Versi dengan visible browser (untuk debugging)
async def search_tiktok_debug(keyword: str):
    """Versi dengan browser yang terlihat untuk debugging"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Jakarta",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
                "Referer": "https://www.google.com/",
                "DNT": "1"
            }
        )
        
        page = await context.new_page()
        
        search_url = f"https://www.tiktok.com/search?q={keyword.replace(' ', '%20')}"
        await page.goto(search_url)
        
        print("⏳ Tunggu 10 detik, lihat apakah muncul video...")
        await page.wait_for_timeout(10000)
        
        # Screenshot untuk lihat hasilnya
        await page.screenshot(path="tiktok_page.png")
        print("📸 Screenshot disimpan ke tiktok_page.png")
        
        # Ambil data
        data = await page.evaluate('''
            () => {
                const links = document.querySelectorAll('a[href*="/video/"]');
                return Array.from(links).map(link => ({
                    url: link.href,
                    text: link.innerText
                }));
            }
        ''')
        
        print(f"\nDitemukan {len(data)} link video")
        
        await browser.close()
        return data

if __name__ == "__main__":
    # Coba dengan debugging dulu jika gagal
    # asyncio.run(search_tiktok_debug("mbg 6 juta hari"))
    asyncio.run(main())