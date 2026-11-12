import { Suspense } from "react";
import AlertsScreen from "@/components/AlertsScreen";

export default function AlertsPage() {
  return (
    <Suspense fallback={null}>
      <AlertsScreen />
    </Suspense>
  );
}
