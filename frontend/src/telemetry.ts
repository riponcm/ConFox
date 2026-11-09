import { init } from '@dash0/sdk-web'

/**
 * Browser monitoring (page views, web vitals, fetch calls, errors) sent to Dash0.
 * Only runs when the build has an endpoint and token. The token ships to every visitor, so it must be an
 * ingest-only token limited to our dataset. Calls to /api are same-origin, so the SDK adds the trace header and
 * the browser span and the API span join into one trace.
 */
export function startTelemetry() {
  const url = import.meta.env.VITE_DASH0_ENDPOINT
  const authToken = import.meta.env.VITE_DASH0_TOKEN
  if (!url || !authToken) return

  init({
    serviceName: 'confox-web',
    environment: 'hackathon',
    endpoint: { url, authToken, dataset: import.meta.env.VITE_DASH0_DATASET || undefined },
  })
}
