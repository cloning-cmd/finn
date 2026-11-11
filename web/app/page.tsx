import { Suspense } from "react";
import BriefScreen from "@/components/BriefScreen";

export default function Home() {
  return (
    <Suspense fallback={null}>
      <BriefScreen />
    </Suspense>
  );
}
