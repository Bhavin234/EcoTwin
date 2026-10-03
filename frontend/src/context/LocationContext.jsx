import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { telemetryApi } from "../api/telemetry";

const LocationContext = createContext(null);

export function LocationProvider({ children }) {
  const [locations, setLocations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = () => {
    setLoading(true);
    setError(null);
    return telemetryApi
      .listLocations()
      .then((data) => {
        setLocations(data);
        setSelectedId((current) => current || data[0]?.id || null);
        setLoading(false);
        return data;
      })
      .catch((err) => {
        setError(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedLocation = useMemo(() => locations.find((l) => l.id === selectedId) || null, [locations, selectedId]);

  const value = { locations, selectedLocation, selectedId, setSelectedId, loading, error, refresh };

  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

export function useLocationContext() {
  const ctx = useContext(LocationContext);
  if (!ctx) throw new Error("useLocationContext must be used within a LocationProvider");
  return ctx;
}
