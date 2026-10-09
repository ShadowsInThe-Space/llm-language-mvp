"use client";
import GeneralApp from "../../generated/tasks/App";

export default function TasksPage() {
  return <GeneralApp endpoint="/api/tasks" />;
}
