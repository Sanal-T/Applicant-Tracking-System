document.addEventListener('DOMContentLoaded', function() {
    // Add debugging information
    console.log('Loading navbar.js');
    console.log('Current page:', window.location.pathname);
    
    // Create the navbar element
    const navbar = document.createElement('div');
    navbar.className = 'navbar';
    
    // Get the current page to highlight the active link
    const currentPage = window.location.pathname.split('/').pop();
    console.log('Current page (processed):', currentPage);
    
    // Check if we're in the smartrecruit directory or frontend directory
    // The paths need to be relative to the current directory
    const isInFrontend = window.location.pathname.includes('frontend/') || 
                         window.location.href.includes('frontend/') ||
                         window.location.href.includes('profile-portal.html') ||
                         window.location.href.includes('resume-analyzer.html') ||
                         window.location.href.includes('database-viewer.html');
    
    console.log('Is in frontend:', isInFrontend);
    
    // User info (get from localStorage if available)
    const userName = localStorage.getItem('userName') || JSON.parse(localStorage.getItem('user'))?.full_name || 'User';
    
    // Build paths based on current directory
    const smartrecruitPath = isInFrontend ? '../smartrecruit/' : '';
    console.log('Smartrecruit path:', smartrecruitPath);
    
    // Navbar HTML
    navbar.innerHTML = `
    <div class="navbar-container">
        <a href="index.html" class="navbar-brand">SmartRecruit</a>
        <div class="navbar-menu">
            <a href="${smartrecruitPath}student-dashboard.html" class="${currentPage === 'student-dashboard.html' || currentPage === 'index.html' || currentPage === '' ? 'active' : ''}">Dashboard</a>
            <a href="profile-portal.html" class="${currentPage === 'profile-portal.html' ? 'active' : ''}">Profile</a>
            <a href="resume-analyzer.html" class="${currentPage === 'resume-analyzer.html' ? 'active' : ''}">Resume Analyzer</a>
            <a href="${smartrecruitPath}jobs-dashboard.html" class="${currentPage === 'jobs-dashboard.html' ? 'active' : ''}">Jobs</a>
            <a href="${smartrecruitPath}applications-dashboard.html" class="${currentPage === 'applications-dashboard.html' ? 'active' : ''}">Applications</a>
            ${
                localStorage.getItem('token') ? 
                `<a href="#" class="logout-btn" id="navLogoutBtn">Logout</a>` :
                `<a href="index.html" class="login-btn">Login</a>`
            }
        </div>
        <div class="navbar-user">
            ${
                localStorage.getItem('token') ? 
                `<span class="user-welcome">Welcome, ${userName}</span>` :
                ''
            }
        </div>
    </div>
    `;
    
    // Prepend navbar to the body
    document.body.prepend(navbar);
    console.log('Navbar added to DOM');
    
    // Add logout functionality
    if (document.getElementById('navLogoutBtn')) {
        document.getElementById('navLogoutBtn').addEventListener('click', function() {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            localStorage.removeItem('userType');
            localStorage.removeItem('userName');
            window.location.href = 'index.html';
        });
    }
    
    // Add CSS styles for the navbar
    const style = document.createElement('style');
    style.textContent = `
    .navbar {
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 0;
        position: sticky;
        top: 0;
        z-index: 1000;
        width: 100%;
        display: block !important; /* Force display */
    }
    
    .navbar-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        max-width: 1200px;
        margin: 0 auto;
        padding: 15px 20px;
    }
    
    .navbar-brand {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2563eb;
        text-decoration: none;
    }
    
    .navbar-menu {
        display: flex;
        gap: 20px;
    }
    
    .navbar-menu a {
        color: #64748b;
        text-decoration: none;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 4px;
        transition: all 0.2s;
    }
    
    .navbar-menu a:hover {
        color: #2563eb;
        background-color: #f0f7ff;
    }
    
    .navbar-menu a.active {
        color: #2563eb;
        background-color: #f0f7ff;
        font-weight: 600;
    }
    
    .navbar-menu a.logout-btn {
        color: #ef4444;
    }
    
    .navbar-menu a.logout-btn:hover {
        background-color: #fee2e2;
    }
    
    .navbar-menu a.login-btn {
        background-color: #2563eb;
        color: white;
    }
    
    .navbar-menu a.login-btn:hover {
        background-color: #1d4ed8;
    }
    
    .navbar-user {
        color: #64748b;
        font-size: 0.9rem;
    }
    
    @media (max-width: 768px) {
        .navbar-container {
            flex-direction: column;
            gap: 15px;
        }
        
        .navbar-menu {
            flex-wrap: wrap;
            justify-content: center;
        }
    }
    `;
    
    document.head.appendChild(style);
}); 