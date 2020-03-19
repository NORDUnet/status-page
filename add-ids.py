import argparse
import yaml


def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)


def section_array(data, section):
    return data.get(section) or []


def main(data_path, dry_run):
    with open(data_path, 'r') as f:
        data = yaml.load(f, Loader=yaml.BaseLoader)

    # check all sections for ids
    all_posts = []
    all_posts = all_posts + (data.get('past') or [])
    all_posts = all_posts + (data.get('planned') or [])
    all_posts = all_posts + (data.get('info') or [])
    all_posts = all_posts + (data.get('current') or [])
    current_ids = set([int(p['id']) for p in all_posts if p.get('id')])

    next_id = max(current_ids) + 1

    for post in all_posts:
        if 'id' not in post:
            print('Add id:', next_id, 'to', post.get('title'))
            post['id'] = next_id
            next_id = next_id + 1
    if not dry_run:
        with open(data_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--data',
        default='data.yml',
        help='Which data file to use when gennerating pages')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Which data file to use when gennerating pages')

    args = parser.parse_args()
    main(args.data, args.dry_run)
