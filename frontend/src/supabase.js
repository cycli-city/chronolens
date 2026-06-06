import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = "https://bvuzawjoajxqnnmbbpjl.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ2dXphd2pvYWp4cW5ubWJicGpsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA3Mjc1ODYsImV4cCI6MjA5NjMwMzU4Nn0.Gk75Lx1F1-b4fGtF3W9XXk6PUAGWXYwaIHY0-Dgz3WE";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);