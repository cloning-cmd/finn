import { Suspense } from "react";
import RulesScreen from "@/components/RulesScreen";

export default function RulesPage() {
  return (
    <Suspense fallback={null}>
      <RulesScreen />
    </Suspense>
  );
}
