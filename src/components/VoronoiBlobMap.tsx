import React, { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { type Project } from "../services/projectsData";
import { ncrCityCenters } from "../services/ncrCityCenters";

type VoronoiBlobMapProps = {
  projects: Project[];
  selectedCity?: string | undefined;
  selectedStatus?: Project["status"] | "all";
  onCitySelect?: (city?: string) => void;
  height?: number | string;
};

const STATUS_COLORS: Record<string, string> = {
  completed: "#10B981",
  ongoing: "#F59E0B",
  proposed: "#3B82F6",
  planning: "#8B5CF6",
};

const NCR_BOUNDS: [[number, number], [number, number]] = [
  [14.31, 120.85], // SW
  [14.85, 121.15], // NE
];

// Helper to get coordinates for a project
function getProjectCoordinates(project: Project): [number, number] | null {
  // Try to get from project itself first
  if (project.latitude && project.longitude) {
    return [project.latitude, project.longitude];
  }

  // Fallback to LGU city center
  if (project.lgu && ncrCityCenters[project.lgu]) {
    return ncrCityCenters[project.lgu];
  }

  return null;
}

// Component to fit bounds when data changes
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

    // Fit to all project bounds
    if (projects.length > 0) {
      const coords = projects
        .map((p) => getProjectCoordinates(p))
        .filter((c) => c !== null) as [number, number][];

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

    // Default NCR center
    map.setView([14.6, 121.02], 11);
  }, [map, projects, selectedCity]);
  return null;
}

// Component to render project blobs with halos
function ProjectBlobs({
  projects,
  selectedCity,
  onCitySelect,
}: {
  projects: Project[];
  selectedCity?: string;
  onCitySelect?: (city?: string) => void;
}) {
  const map = useMap();
  const layerGroupRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    if (!map || !layerGroupRef.current) return;

    // Clear previous layers
    layerGroupRef.current.clearLayers();

    projects.forEach((project) => {
      const coords = getProjectCoordinates(project);
      if (!coords) return;

      const statusColor = STATUS_COLORS[project.status] || "#94A3B8";
      const isSelected = selectedCity ? project.lgu === selectedCity : false;

      // Outer glow circle (halo effect)
      const haloRadius = isSelected ? 3000 : 2000; // meters
      const haloCircle = L.circle(coords, {
        radius: haloRadius,
        color: statusColor,
        fillColor: statusColor,
        fillOpacity: isSelected ? 0.25 : 0.1,
        weight: 0,
        interactive: false,
      });

      // Main blob circle
      const blobRadius = isSelected ? 1500 : 800; // meters
      const blobCircle = L.circle(coords, {
        radius: blobRadius,
        color: statusColor,
        fillColor: statusColor,
        fillOpacity: isSelected ? 0.5 : 0.3,
        weight: isSelected ? 2 : 1,
        dashArray: isSelected ? "5,5" : undefined,
      });

      // Create popup with project info
      const popupContent = `
        <div style="padding: 8px; max-width: 200px;">
          <h4 style="margin: 0 0 4px 0; font-weight: bold; font-size: 14px;">${project.title}</h4>
          <p style="margin: 2px 0; font-size: 12px; color: #666;">${project.agency || "N/A"}</p>
          <p style="margin: 2px 0; font-size: 12px; color: #666;">${project.lgu}</p>
          <p style="margin: 4px 0; font-size: 12px; font-weight: bold; color: #059669;">
            ₱ ${(project.budget || 0).toLocaleString()}
          </p>
          <span style="display: inline-block; background: ${statusColor}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase;">
            ${project.status}
          </span>
        </div>
      `;

      blobCircle.bindPopup(popupContent);

      // Click handler
      blobCircle.on("click", () => {
        if (onCitySelect) {
          onCitySelect(project.lgu);
        }
      });

      // Hover effects
      blobCircle.on("mouseover", () => {
        blobCircle.setStyle({
          fillOpacity: 0.7,
          weight: 2,
        });
        haloCircle.setStyle({
          fillOpacity: 0.35,
        });
        blobCircle.openPopup();
      });

      blobCircle.on("mouseout", () => {
        blobCircle.setStyle({
          fillOpacity: isSelected ? 0.5 : 0.3,
          weight: isSelected ? 2 : 1,
        });
        haloCircle.setStyle({
          fillOpacity: isSelected ? 0.25 : 0.1,
        });
      });

      layerGroupRef.current?.addLayer(haloCircle);
      layerGroupRef.current?.addLayer(blobCircle);
    });
  }, [projects, selectedCity, map, onCitySelect]);

  useEffect(() => {
    if (!map) return;

    if (!layerGroupRef.current) {
      layerGroupRef.current = L.featureGroup().addTo(map);
    }

    return () => {
      if (layerGroupRef.current) {
        layerGroupRef.current.clearLayers();
      }
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
          projects={projects}
          selectedCity={selectedCity}
          onCitySelect={onCitySelect}
        />
        <FitBoundsToProjects projects={projects} selectedCity={selectedCity} />
      </MapContainer>
    </div>
  );
};

export default VoronoiBlobMap;
