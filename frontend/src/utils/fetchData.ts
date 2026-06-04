import { api } from "../services/api";

export async function fetchData<T>(endpoint: string): Promise<T> {
  return api.get(endpoint) as Promise<T>;
}
