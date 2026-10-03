import { useEffect, useRef } from "react";

// Cloudflare's "always passes" test site key - safe to use for local dev
// before you have real Turnstile keys. Replace via VITE_TURNSTILE_SITE_KEY
// in .env once you've set one up at https://dash.cloudflare.com/?to=/:account/turnstile
const DEFAULT_TEST_SITE_KEY = "1x00000000000000000000AA";

export default function Turnstile({ onVerify, onExpire }) {
    const containerRef = useRef(null);
    const widgetId = useRef(null);

    useEffect(() => {
        let cancelled = false;
        let pollId;

        const tryRender = () => {
            if (cancelled) return;
            if (window.turnstile && containerRef.current) {
                widgetId.current = window.turnstile.render(containerRef.current, {
                    sitekey: import.meta.env.VITE_TURNSTILE_SITE_KEY || DEFAULT_TEST_SITE_KEY,
                    callback: onVerify,
                    "expired-callback": () => onExpire?.(),
                });
            } else {
                pollId = setTimeout(tryRender, 200);
            }
        };
        tryRender();

        return () => {
            cancelled = true;
            clearTimeout(pollId);
            if (window.turnstile && widgetId.current != null) {
                window.turnstile.remove(widgetId.current);
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return <div ref={containerRef} className="flex justify-center" />;
}
