import posthog from 'posthog-js'

const POSTHOG_KEY = import.meta.env.VITE_POSTHOG_KEY || ''
const POSTHOG_HOST = import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com'

if (POSTHOG_KEY) {
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    capture_pageview: true,
    autocapture: true,
    // Session replay disabled for now
    disable_session_recording: true,
    // Web vitals (LCP, CLS, INP)
    capture_performance: true,
    // Error tracking
    capture_exceptions: true,
  })
}

export default posthog
