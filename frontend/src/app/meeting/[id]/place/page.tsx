"use client";

import { useEffect } from "react";
import { useRouter, useParams } from "next/navigation";

export default function PlaceRedirect() {
  const router = useRouter();
  const params = useParams();
  useEffect(() => {
    router.replace(`/meeting/${params.id}`);
  }, [router, params.id]);
  return null;
}
