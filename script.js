// API Base URL - Will be your Render service URL
const API_BASE = 'https://dramawallah-bot.onrender.com';

// Load dynamic content from MongoDB
async function loadDynamicContent() {
    try {
        console.log('Loading content from API...');
        
        const [dramas, ongoing, news] = await Promise.all([
            fetch(`${API_BASE}/api/dramas`).then(r => r.json()),
            fetch(`${API_BASE}/api/ongoing`).then(r => r.json()),
            fetch(`${API_BASE}/api/news`).then(r => r.json())
        ]);

        updateDramasSection(dramas);
        updateOngoingSection(ongoing);
        updateNewsSection(news);
        
    } catch (error) {
        console.log('Using static content as fallback');
        // Your existing static content remains as fallback
    }
}

function updateDramasSection(dramas) {
    const container = document.querySelector('.cards-grid');
    if (!container || !dramas) return;

    container.innerHTML = dramas.map(drama => `
        <div class="card" data-title="${drama.name.toLowerCase()}">
            <div class="poster">
                ${drama.poster_image ? 
                    `<img src="${drama.poster_image}" alt="${drama.name}" style="width:100%;height:100%;object-fit:cover">` :
                    'POSTER IMAGE'
                }
            </div>
            <div class="content">
                <h3 class="title">${drama.name}</h3>
                <a href="${drama.channel_link}" target="_blank" class="download-btn">download now</a>
            </div>
        </div>
    `).join('');
}

// Call this when page loads
document.addEventListener('DOMContentLoaded', loadDynamicContent);
