import { useState } from "react";
import { useLocationContext } from "../../context/LocationContext";
import { Button } from "../common/Primitives";
import DemoRunner from "./DemoRunner";
import "./TopBar.css";

export default function TopBar() {
  const { selectedLocation, loading } = useLocationContext();
  const [demoOpen, setDemoOpen] = useState(false);

  return (
    <header className="topbar">
      <div className="topbar__location">
        {!loading && selectedLocation ? (
          <>
            <span className="topbar__location-label">Monitoring</span>
            <span className="topbar__location-name">{selectedLocation.name}</span>
          </>
        ) : (
          <span className="topbar__location-label">No location data yet</span>
        )}
      </div>
      <Button onClick={() => setDemoOpen(true)}>Run EcoTwin Demo</Button>
      {demoOpen && <DemoRunner onClose={() => setDemoOpen(false)} />}
    </header>
  );
}
