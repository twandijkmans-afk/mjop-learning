-- MJOP Live 3 — gevelfoto's bewaren in Supabase Storage.
--
-- Een privé bucket `gevelfotos`. Elke foto staat onder de map van zijn project: {project_id}/gevel-{zijde}-{deel}.jpg.
-- Lezen mag wie het project mag zien (eigenaar of lid); uploaden, vervangen en verwijderen mag de eigenaar of een bewerker.
-- Daarnaast een kolom photo_path in projects: de eigen gevelfoto die de app als projectfoto toont (anders de luchtfoto).
-- Veilig om vaker uit te voeren.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('gevelfotos', 'gevelfotos', false, 10485760, array['image/jpeg'])
on conflict (id) do nothing;

alter table public.projects add column if not exists photo_path text;

-- Lezen: het project moet zichtbaar zijn voor de gebruiker (de RLS van projects bepaalt dat: eigenaar of lid).
drop policy if exists "gevelfotos lezen" on storage.objects;
create policy "gevelfotos lezen" on storage.objects for select to authenticated
    using (bucket_id = 'gevelfotos'
           and exists (select 1 from public.projects p where p.id::text = (storage.foldername(name))[1]));

-- Schrijven: eigenaar of bewerker van het project.
drop policy if exists "gevelfotos uploaden" on storage.objects;
create policy "gevelfotos uploaden" on storage.objects for insert to authenticated
    with check (bucket_id = 'gevelfotos'
                and exists (select 1 from public.projects p where p.id::text = (storage.foldername(name))[1]
                            and (p.owner_id = auth.uid() or public.is_project_member(p.id, array['eigenaar', 'bewerker']))));

drop policy if exists "gevelfotos vervangen" on storage.objects;
create policy "gevelfotos vervangen" on storage.objects for update to authenticated
    using (bucket_id = 'gevelfotos'
           and exists (select 1 from public.projects p where p.id::text = (storage.foldername(name))[1]
                       and (p.owner_id = auth.uid() or public.is_project_member(p.id, array['eigenaar', 'bewerker']))));

drop policy if exists "gevelfotos verwijderen" on storage.objects;
create policy "gevelfotos verwijderen" on storage.objects for delete to authenticated
    using (bucket_id = 'gevelfotos'
           and exists (select 1 from public.projects p where p.id::text = (storage.foldername(name))[1]
                       and (p.owner_id = auth.uid() or public.is_project_member(p.id, array['eigenaar', 'bewerker']))));
