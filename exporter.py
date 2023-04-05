#!/usr/bin/env python3

from pathlib import Path
import re
import sys
import requests as req

import lea
from utils import *

from anytree import Node, RenderTree

all_notes = {}

def _get_parent_node(nb_id, id_to_parent_id, id_to_node, id_to_title, root_node):
    """Get parent node of notebook @nb_id.
    """
    parent_id = id_to_parent_id.get(nb_id)
    if not parent_id:  # Without parent.
        return root_node

    if parent_id not in id_to_node: # Parent node not create yet.
        parent_node = Node(id_to_title[parent_id], parent=_get_parent_node(
            parent_id, id_to_parent_id, id_to_node, id_to_title, root_node
        ), id=parent_id)
        id_to_node[parent_id] = parent_node
    else:
        parent_node = id_to_node.get(parent_id)
    return parent_node

def get_notebooks_paths(notebooks):
    """Get local paths for notebooks.

    Args:
        notebooks: List of notebooks' info.

    Returns:
        Dict that maps a notebook's id to its path.
    """
    notebooks = [nb for nb in notebooks if not nb['IsDeleted']]

    # Get floders' tree
    id_to_title = {nb['NotebookId']: nb['Title'] for nb in notebooks}
    id_to_parent_id = {nb['NotebookId']: nb['ParentNotebookId'] for nb in notebooks}
    id_to_node = {}
    tree_root = Node('.')
    for nb_id in id_to_parent_id.keys():
        if nb_id not in id_to_node:
            node = Node(id_to_title[nb_id], parent=_get_parent_node(
                nb_id, id_to_parent_id, id_to_node, id_to_title, tree_root
            ), id=nb_id)
            id_to_node[nb_id] = node

    # Get paths of notebooks
    nb_id_to_paths = {}
    for node in tree_root.descendants:
        path = Path()
        for nd in node.path:
            path = path / nd.name.strip()
        nb_id_to_paths[node.id] = path
    return nb_id_to_paths

def save_image(url, img_path, forced_save=False):
    """Download image from @url and save it to @img_path.

    Args:
        url: Url of image.
        img_path: Path to save the image.
        forced_save: Force to save images if True.

    Returns:
        Filename
    """
    def get_image(url):
        r = req.get(url)
        if r.status_code != req.codes.ok:
            print('Failed to get image %s' % (url))
            return ''
        fname = ''
        if "Content-Disposition" in r.headers.keys():
            fname = re.findall("filename=(.+)", r.headers["Content-Disposition"])[0]
        else:
            fname = url.split("/")[-1]
        return r.content, fname

    if '/api/file/getImage' in url:
        image_id = re.sub(r'.*fileId=(.*).*', r'\1', url)

        img, filename = lea.get_image(image_id)

        if filename == '':
            filename = image_id + '.png'
        file_path = Path(img_path) / filename
        print('Saving image %s' % (file_path))
        if not os.path.exists(file_path) or forced_save:
            with open(file_path, 'wb') as f:
                f.write(img)
        return filename
    elif config.img_external:
        img, filename = get_image(url)

        file_path = Path(img_path) / filename
        print('Saving image %s' % (file_path))
        if not os.path.exists(file_path) or forced_save:
            with open(file_path, 'wb') as f:
                f.write(img)
        return filename
    else:
        return url

def save_attach(url, path, forced_save=False):
    """Download attachment from @url and save it to @path.

    Args:
        url: Url of attachment.
        path: Path to save the attachment.
        forced_save: Force to save attachments if True.

    Returns:
        Filename
    """
    if '/api/file/getAttach' in url:
        file_id = re.sub(r'.*fileId=(.*).*', r'\1', url)

        content, filename = lea.get_attach(file_id)
        if filename == '':
            filename = file_id
        file_path = Path(path) / filename
        print('Saving attachment %s' % (file_path))
        if not os.path.exists(file_path) or forced_save:
            with open(file_path, 'wb') as f:
                f.write(content)
        return filename
    elif '/api/file/getImage' in url:
        return save_image(url, path, forced_save)
    else:
        return url

def localize_image_link(content, final_path, config):
    """Localize image links in @content.

    Download all images in content, change the link to local path.

    Args:
        content: Content to parse.
        final_path: Output path.
        config: Configuration.
    """
    img_path = Path(config.img_path)
    if not img_path.is_absolute():
        img_path = final_path / img_path
    mkdir_p(img_path)

    img_link_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
    def _change_link(m):
        url = m.group(2)
        filename = save_image(url, img_path, config.forced_save)
        if filename == url or filename == '':
            return m.group(0)
        return '![{}]({})'.format(m.group(1), config.img_link_path + '/' + filename)

    return img_link_pattern.sub(_change_link, content)

def localize_attach_link(content, final_path, config):
    """Localize attachment links in @content.

    Download all attachments in content, change the link to local path.

    Args:
        content: Content to parse.
        final_path: Output path.
        config: Configuration.
    """
    path = Path(config.attach_path)
    if not path.is_absolute():
        path = final_path / path
    mkdir_p(path)

    link_pattern = re.compile(r'\[(.*?)\]\((.*?)\)')
    def _change_link(m):
        url = m.group(2)
        filename = save_attach(url, path, config.forced_save)
        if filename == url or filename == '':
            return m.group(0)
        return '[{}]({})'.format(m.group(1), config.attach_link_path + '/' + filename)

    return link_pattern.sub(_change_link, content)

def save_note_as_md(note, nb_id_to_paths, config):
    """Save note to $output_path and referenced images to $img_path.

    Args:
        note: Note to save.
        nb_id_to_paths: Dict that map notebook's id to its path.
        config: Configuration.
        add_hexo_meta: Add hexo meta header at the beginning of the note if True.
    """
    if note['IsTrash'] or not note['IsMarkdown']:
        return
    if config.only_blog and not note['IsBlog']:
        return

    title = note['Title']
    if note['Tags']:
        tags = ''.join(['\n- ' + t for t in note['Tags']])
    else:
        tags = ''
    created_time = note['CreatedTime']
    content = note['Content']

    hexo_meta_header = {
        'title': title,
        'date': created_time,
        'tags': tags,
    }

    final_path = Path(config.output_path)
    folder = nb_id_to_paths.get(note['NotebookId'])
    if folder:
        final_path /= folder
    mkdir_p(final_path)

    title = title.strip()
    title = windows_filename_filter(title)
    title += '.md'
    filepath = final_path / title
    print('Saving note %s' % (filepath))

    if config.localize_image:
        content = localize_image_link(content, final_path, config)
    if config.localize_attach:
        content = localize_attach_link(content, final_path, config)

    try:
        with open(filepath, 'w', encoding='utf-8') as fd:
            if config.output_meta:
                fd.write('---\n')
                for h in hexo_meta_header:
                    fd.write('%s: %s\n' % (h, hexo_meta_header[h]))
                fd.write('---\n')
            fd.write(content)
    except OSError as e:
        print(e)

    all_notes[note['NotebookId']] = filepath


if __name__ == '__main__':
    import config

    lea.login(config.host, config.email, config.pwd)
    notebooks = lea.get_notebooks()
    nb_id_to_paths = get_notebooks_paths(notebooks)

    for nb in notebooks:
        notes = lea.get_notes(nb['NotebookId'])
        for note in notes:
            note = lea.get_note(note['NoteId'])
            save_note_as_md(note, nb_id_to_paths, config)

    print(all_notes)
