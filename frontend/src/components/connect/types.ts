// Shapes returned by /api/connect. Meetings are agenda documents with kind "meeting".

/** A food or coffee break both people are free for (GET /api/connect/slots). */
export type Slot = {
  session_id: string
  title: string
  starts_at: string
  ends_at: string
  room?: string | null
  day: string
}

export type SlotsResponse = { slots: Slot[] }

export type Meeting = {
  id: string
  kind: 'meeting'
  status: 'pending' | 'confirmed' | 'declined' | 'withdrawn'
  /** A pending meeting without a direction is a request someone sent the user. */
  direction?: 'incoming' | 'outgoing'
  with_id: string
  with_name: string
  title: string
  starts_at: string
  ends_at: string
  room?: string | null
  session_id?: string
  message?: string
  sample?: boolean
}

/** GET /api/connect */
export type ConnectResponse = { incoming: Meeting[]; outgoing: Meeting[]; meetings: Meeting[] }
