"use client";

import CalendarPane from "@/components/meeting/CalendarPane";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";
import { useMeeting } from "@/contexts/MeetingContext";

const PANE_WIDTH = 414;
const PANE_HEIGHT = 733;
const COLLAPSED_CALENDAR_HEIGHT = 200;
const SECTION_GAP = 12;

export default function InfoPane() {
  const { selectedPlace } = useMeeting();
  const hasSelectedPlace = selectedPlace !== null;
  const placeDetailAvailableHeight = PANE_HEIGHT - COLLAPSED_CALENDAR_HEIGHT - SECTION_GAP;
  const placeDetailScale = placeDetailAvailableHeight / PANE_HEIGHT;

  return (
    <div
      style={{
        width: PANE_WIDTH,
        height: PANE_HEIGHT,
        display: "flex",
        flexDirection: "column",
        gap: SECTION_GAP,
      }}
    >
      <div
        style={{
          height: hasSelectedPlace ? COLLAPSED_CALENDAR_HEIGHT : "100%",
          overflow: "hidden",
          borderRadius: 20,
          flexShrink: 0,
        }}
      >
        <CalendarPane />
      </div>

      {hasSelectedPlace && (
        <div
          style={{
            height: placeDetailAvailableHeight,
            overflow: "hidden",
            borderRadius: 20,
            flexShrink: 0,
          }}
        >
          <div
            style={{
              width: PANE_WIDTH / placeDetailScale,
              height: PANE_HEIGHT,
              transform: `scale(${placeDetailScale})`,
              transformOrigin: "top left",
            }}
          >
            <PlaceDetailPane place={selectedPlace} />
          </div>
        </div>
      )}
    </div>
  );
}
