import { create } from 'zustand';
import { fetchPets, fetchTypes } from '../utils/api';
import type { Pet, TypeInfo } from '../utils/api';

interface PetsState {
  pets: Pet[];
  total: number;
  types: TypeInfo[];
  loading: boolean;
  searchName: string;
  page: number;
  pageSize: number;
  setSearchName: (name: string) => void;
  setPage: (page: number) => void;
  loadPets: () => Promise<void>;
  loadTypes: () => Promise<void>;
}

export const usePetsStore = create<PetsState>((set, get) => ({
  pets: [],
  total: 0,
  types: [],
  loading: false,
  searchName: '',
  page: 1,
  pageSize: 20,
  setSearchName: (name) => set({ searchName: name, page: 1 }),
  setPage: (page) => set({ page }),
  loadPets: async () => {
    set({ loading: true });
    const { searchName, page, pageSize } = get();
    try {
      const data = await fetchPets({
        name: searchName || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      set({ pets: data.pets, total: data.total, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  loadTypes: async () => {
    const data = await fetchTypes();
    set({ types: data.types });
  },
}));
