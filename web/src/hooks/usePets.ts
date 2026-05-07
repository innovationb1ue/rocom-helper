import { useEffect } from 'react';
import { usePetsStore } from '../stores/petsStore';

export function usePets() {
  const { pets, total, types, loading, searchName, page, pageSize,
    setSearchName, setPage, loadPets, loadTypes } = usePetsStore();

  useEffect(() => { loadTypes(); }, [loadTypes]);
  useEffect(() => { loadPets(); }, [searchName, page, loadPets]);

  return { pets, total, types, loading, searchName, page, pageSize,
    setSearchName, setPage, loadPets };
}
