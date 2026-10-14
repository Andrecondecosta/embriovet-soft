import { createContext, useContext } from "react";
import type { User } from "../api/types";

export const UserContext = createContext<User | null>(null);

export function useUser(): User {
  const user = useContext(UserContext);
  if (!user) throw new Error("useUser fora de uma sessão");
  return user;
}

export const useIsAdmin = () => useUser().nivel === "Administrador";
