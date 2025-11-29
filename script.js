// Add this to your existing website
const API_BASE = 'https://dramawallah-bot.onrender.com';

async function loadDynamicContent() {
    try {
        const [dramasRes, ongoingRes, newsRes] = await Promise.all([
            fetch(`${API_BASE}/api/dramas`),
            fetch(`${API_BASE}/api/ongoing`),
            fetch(`${API_BASE}/api/news`)
        ]);

        const dramas = await dramasRes.json();
        const ongoing = await ongoingRes.json();
        const news = await newsRes.json();

        if (dramas.success) updateSection('dramas-container', dramas.data);
        if (ongoing.success) updateSection('ongoing-container', ongoing.data);
        if (news.success) updateNewsSection('news-container', news.data);
        
    } catch (error) {
        console.log('using static content');
    }
}

function updateSection(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container || !items) return;

    container.innerHTML = items.map(item => `
        <div class="card" data-title="${item.name.toLowerCase()}">
            <div class="poster">
                ${item.poster_image ? 
                    `<img src="${item.poster_image}" alt="${item.name}" style="width:100%;height:100%;object-fit:cover">` :
                    'POSTER IMAGE'
                }
            </div>
            <div class="content">
                <h3 class="title">${item.name}</h3>
                <a href="${item.channel_link}" target="_blank" class="download-btn">download now</a>
            </div>
        </div>
    `).join('');
}

function updateNewsSection(containerId, newsItems) {
    const container = document.getElementById(containerId);
    if (!container || !newsItems) return;

    container.innerHTML = newsItems.map(news => `
        <div class="news-card">
            <div class="news-image">
                ${news.image ? 
                    `<img src="${news.image}" alt="${news.title}" style="width:100%;height:100%;object-fit:cover">` :
                    'NEWS IMAGE'
                }
            </div>
            <div class="news-content">
                <h3 class="news-title">${news.title}</h3>
                <p class="news-excerpt">${news.content.substring(0, 100)}...</p>
                <a href="#" class="read-more">read more →</a>
            </div>
        </div>
    `).join('');
}

document.addEventListener('DOMContentLoaded', loadDynamicContent);
