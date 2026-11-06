/** OAK box's own settings on this computer (routes/app_settings.py): asked once, shared by every screen. */
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";

export const appSettingsKey = ["app-settings"] as const;

export function useAppSettings() {
  return useQuery({
    queryKey: appSettingsKey,
    queryFn: async () => unwrap(await api.GET("/api/app-settings")),
  });
}
