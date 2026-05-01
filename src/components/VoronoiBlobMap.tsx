import React, { useEffect, useMemo, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { type PublicProject as Project } from "../services/publicProjectsApi";
import { ncrCityCenters } from "../services/ncrCityCenters";

type VoronoiBlobMapProps = {
  projects: Project[];
  selectedCity?: string | undefined;
  selectedStatus?: string | "all";
  onCitySelect?: (city?: string) => void;
  height?: number | string;
};

const STATUS_COLORS: Record<string, string> = {
  Completed: "#10B981",
  Ongoing: "#F59E0B",
  New: "#3B82F6",
  Updated: "#6366F1",
  Discontinued: "#EF4444",
  "Not Implemented": "#94A3B8",
  Dropped: "#F97316",
  "N/A": "#64748B",
  Unspecified: "#94A3B8",
};

const NCR_BOUNDS: [[number, number], [number, number]] = [
  [14.31, 120.85], // SW
  [14.85, 121.15], // NE
];

type CityGroup = {
  city: string;
  coords: [number, number];
  projects: Project[];
  count: number;
  dominantStatus: string;
  color: string;
};

function getProjectCoordinates(project: Project): [number, number] | null {
  if (project.lgu && ncrCityCenters[project.lgu]) {
    return ncrCityCenters[project.lgu];
  }
  return null;
}

function FitBoundsToProjects({
  projects,
  selectedCity,
}: {
  projects: Project[];
  selectedCity?: string;
}) {
  const map = useMap();
  useEffect(() => {
    if (!map) return;
    if (selectedCity && ncrCityCenters[selectedCity]) {
      const [lat, lng] = ncrCityCenters[selectedCity];
      map.setView([lat, lng], 12, { animate: true });
      return;
    }

    if (projects.length > 0) {
      const coords = projects
        .map((p) => getProjectCoordinates(p))
        .filter((c): c is [number, number] => Boolean(c));

      if (coords.length === 0) {
        map.setView([14.6, 121.02], 11);
        return;
      }
      if (coords.length === 1) {
        map.setView(coords[0], 12, { animate: true });
        return;
      }

      const bounds = L.latLngBounds(coords);
      bounds.pad(0.15);
      map.fitBounds(bounds, { animate: true, maxZoom: 13 });
      return;
    }

    map.setView([14.6, 121.02], 11);
  }, [map, projects, selectedCity]);
  return null;
}

function ProjectBlobs({
  groups,
  selectedCity,
  onCitySelect,
}: {
  groups: CityGroup[];
  selectedCity?: string;
  onCitySelect?: (city?: string) => void;
}) {
  const map = useMap();
  const layerGroupRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    if (!map || !layerGroupRef.current) return;
    layerGroupRef.current.clearLayers();

    groups.forEach((group) => {
      const coords = group.coords;
      const statusColor = group.color;
      const isSelected = selectedCity ? group.city === selectedCity : false;

      const haloRadius = isSelected ? 3200 : 2200;
      const haloCircle = L.circle(coords, {
        radius: haloRadius,
        color: statusColor,
        fillColor: statusColor,
        fillOpacity: isSelected ? 0.25 : 0.1,
        weight: 0,
        interactive: false,
      });

      const baseRadius = 700 + Math.min(1600, group.count * 180);
      const blobRadius = isSelected
        ? Math.max(1100, baseRadius + 500)
        : baseRadius;
      const blobCircle = L.circle(coords, {
        radius: blobRadius,
        color: statusColor,
        fillColor: statusColor,
        fillOpacity: isSelected ? 0.5 : 0.3,
        weight: isSelected ? 2 : 1,
        dashArray: isSelected ? "5,5" : undefined,
      });

      const preview = group.projects
        .slice(0, 5)
        .map(
          (p) =>
            `<li style="margin:2px 0; font-size:12px;"><strong style="color:#0ea5a6;">${
              (p.implementation_status || "Unspecified").toString()
            }</strong> — ${String(p.title || "")}</li>`,
        )
        .join("");
      const remainder =
        group.count > 5
          ? `<div style="margin-top:6px; font-size:12px;">+${
              group.count - 5
            } more</div>`
          : "";

      const popupContent = `
        <div style="padding: 8px; max-width: 280px;">
          <h4 style="margin: 0 0 4px 0; font-weight: bold; font-size: 14px;">${
            group.city
          }</h4>
          <p style="margin: 2px 0; font-size: 12px; color: #475569;">${
            group.count
          } project(s)</p>
          <span style="display: inline-block; background: ${statusColor}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase;">
            ${String(group.dominantStatus || "Unspecified")}
          </span>
          <ul style="margin-top:8px; padding-left:16px;">${preview}</ul>
          ${remainder}
        </div>
      `;

      blobCircle.bindPopup(popupContent);

      blobCircle.on("click", () => {
        if (onCitySelect) onCitySelect(group.city);
      });

      blobCircle.on("mouseover", () => {
        blobCircle.setStyle({ fillOpacity: 0.7, weight: 2 });
        haloCircle.setStyle({ fillOpacity: 0.35 });
        blobCircle.openPopup();
      });

      blobCircle.on("mouseout", () => {
        blobCircle.setStyle({
          fillOpacity: isSelected ? 0.5 : 0.3,
          weight: isSelected ? 2 : 1,
        });
        haloCircle.setStyle({ fillOpacity: isSelected ? 0.25 : 0.1 });
      });

      layerGroupRef.current?.addLayer(haloCircle);
      layerGroupRef.current?.addLayer(blobCircle);
    });
  }, [groups, selectedCity, map, onCitySelect]);

  useEffect(() => {
    if (!map) return;
    if (!layerGroupRef.current) {
      layerGroupRef.current = L.featureGroup().addTo(map);
    }
    return () => {
      if (layerGroupRef.current) layerGroupRef.current.clearLayers();
    };
  }, [map]);

  return null;
}

const VoronoiBlobMap: React.FC<VoronoiBlobMapProps> = ({
  projects,
  selectedCity,
  onCitySelect,
  height = 600,
}) => {
  const groups = useMemo(() => {
    const byCity: Record<string, Project[]> = {};
    projects.forEach((p) => {
      const city = p.lgu;
      if (!city) return;
      if (!ncrCityCenters[city]) return;
      if (!byCity[city]) byCity[city] = [];
      byCity[city].push(p);
    });

    return Object.entries(byCity).map(([city, ps]) => {
      const counts: Record<string, number> = {};
      ps.forEach((p) => {
        const st =
          (p.implementation_status || "Unspecified").trim() || "Unspecified";
        counts[st] = (counts[st] || 0) + 1;
      });
      let dominant = "Unspecified";
      let max = -1;
      Object.entries(counts).forEach(([st, c]) => {
        if (c > max) {
          max = c;
          dominant = st;
        }
      });
      const color = STATUS_COLORS[dominant] || "#94A3B8";
      return {
        city,
        coords: ncrCityCenters[city],
        projects: ps,
        count: ps.length,
        dominantStatus: dominant,
        color,
      } as CityGroup;
    });
  }, [projects]);

  return (
    <div
      style={{
        height: typeof height === "string" ? height : `${height}px`,
        borderRadius: "0.75rem",
        overflow: "hidden",
      }}
    >
      <MapContainer
        center={[14.6, 121.02]}
        zoom={11}
        style={{ height: "100%", width: "100%" }}
        maxBounds={NCR_BOUNDS}
        maxBoundsViscosity={1.0}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ProjectBlobs
          groups={groups}
          selectedCity={selectedCity}
          onCitySelect={onCitySelect}
        />
        <FitBoundsToProjects projects={projects} selectedCity={selectedCity} />
      </MapContainer>
    </div>
  );
};

export default VoronoiBlobMap;

