export function Topbar() {
  return (
    <header className="topbar">
      <div className="marker">monitoring / Dashboard</div>
      <div className="marker">UTC · {new Date().toISOString().slice(11, 19)}</div>
    </header>
  );
}
