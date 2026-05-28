(function() {
    const log = (status, phone, data) => {
        console.log(
            `%c[${status}] %c${phone}`,
            `color: ${status === 'ALIVE' ? 'lime' : 'red'}; font-weight: bold`,
            'color: white',
            data
        );
    };

    // ── 1. Hook Fetch API ──────────────────────────────────────
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const response = await originalFetch.apply(this, args);
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;

        if (url && (url.includes('friend') || url.includes('profile') || url.includes('search'))) {
            const clone = response.clone();
            clone.json().then(data => {
                const phone = new URL(url).searchParams.get('phone') || '???';
                if (data?.data?.uid) {
                    log('ALIVE ✅', phone, {
                        uid:    data.data.uid,
                        name:   data.data.display_name,
                        avatar: data.data.avatar
                    });
                } else {
                    log('DEAD ❌', phone, { error_code: data?.error });
                }
            }).catch(() => {});
        }
        return response;
    };

    // ── 2. Hook XMLHttpRequest (fallback) ─────────────────────
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url) {
        this._url = url;
        return originalOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function() {
        this.addEventListener('load', function() {
            if (!this._url) return;
            if (this._url.includes('friend') || this._url.includes('search')) {
                try {
                    const data = JSON.parse(this.responseText);
                    const phone = new URL(this._url, location.origin)
                                    .searchParams.get('phone') || '???';
                    if (data?.data?.uid) {
                        log('ALIVE ✅', phone, data.data);
                    } else {
                        log('DEAD ❌', phone, { error_code: data?.error });
                    }
                } catch(e) {}
            }
        });
        return originalSend.apply(this, arguments);
    };

    console.log('%c[Hook Active] Đang lắng nghe request...', 'color: cyan; font-size: 14px');
})();