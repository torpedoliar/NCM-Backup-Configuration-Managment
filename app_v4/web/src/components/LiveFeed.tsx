import { useLiveActivity } from '../store/liveActivity';

export function LiveFeed() {
  const events = useLiveActivity((state) => state.events);
  return <section><div className="marker">/LIVE FEED</div>{events.length === 0 ? <p>No events yet.</p> : events.map((event, index) => <p key={`${event.ts}-${index}`}>{event.type}</p>)}</section>;
}
