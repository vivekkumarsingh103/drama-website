// Load dynamic content from MongoDB
async function loadContent() {
    try {
        const [dramas, ongoing, news] = await Promise.all([
            fetch('/api/dramas').then(r => r.json()),
            fetch('/api/ongoing').then(r => r.json()),
            fetch('/api/news').then(r => r.json())
        ]);
        
        updateDramasSection(dramas);
        updateOngoingSection(ongoing);
        updateNewsSection(news);
    } catch (error) {
        console.error('Failed to load content:', error);
    }
}

function updateDramasSection(dramas) {
    const container = document.getElementById('dramas-container');
    container.innerHTML = dramas.map(drama => `
        <div class="card" data-title="${drama.name.toLowerCase()}">
            <div class="poster" style="background-image: url('${drama.poster_image}')"></div>
            <div class="content">
                <h3 class="title">${drama.name}</h3>
                <a href="${drama.channel_link}" target="_blank" class="download-btn">download now</a>
            </div>
        </div>
    `).join('');
}

// Call on page load
document.addEventListener('DOMContentLoaded', loadContent);
