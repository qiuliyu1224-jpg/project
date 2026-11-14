# VoteLab 0.4.5 - Repeated-launch recovery

���������Ѵ���Ա�ṩ���ն˴������������õ�ȷ�ϣ�Mac �Ͼ� VoteLab ���ں�̨���У��ظ�����ʱĬ�� 8765 �˿ڲ��� `Address already in use`��ֱ�Ӵ� http://127.0.0.1:8765/ ���Կ��� VoteLab��

- ͬһ�û�����Ŀ¼ʹ�ò���ϵͳ�ļ��������������°�������ͬʱ��ʼ��ͬһ�����ݿ⣻���̽��������ϵͳ�ͷ�����
- 0.4.5 �ظ������Ⱥ˶Ա���ʵ�����ƣ��ٴ�������ʵ����ͬһ��ַ�������� VoteLab �����������жϷ������ݡ�
- �ɰ� 0.4.4 û���°�ʵ�����ݽӿڡ�����ǰӦ���˳���֪�� VoteLab���޷�ȷ�����ݵĶ˿�ռ�û���ȷ���������Զ����˿ڻ�ֹͣ���������������ݿⱸ�ݺ�Ǩ��֮ǰֹͣ��
- ������־ʼ��д��ԭ�û�����Ŀ¼�� launcher.log����¼�ɽ��� Python �׶ε���������Mac �������ͬʱ��ʾ����ʧ��˵����Python ����ǰ��ϵͳ���ػ����ʧ���Կ���������־������
- Windows ʹ�ö�ռ�˿ڰ󶨣����⸴���ѱ����� HTTP ����ռ�õĵ�ַ��ԭ�� SQLite ����λ�á�����ǰ���ݺ�ͶƱ���ܼ���������

This release addresses the confirmed Mac error when opening VoteLab again while its local server is already running. A per-data-directory OS lock prevents a second new launcher from initializing the same database. Authenticated local instance discovery reopens the existing page. Unknown port occupants and legacy instances without the new identity endpoint produce clear guidance before database backup or migration. There is no automatic port switch or process termination.

Startup logging is independent of console availability. The packaged Mac app displays Python-stage startup failures. Windows uses exclusive port binding. Existing user data paths and SQLite startup backups are retained. Closing a browser tab still does not stop the app.

Validation required before publication: the full regression suite, process-level duplicate-launch/occupied-port/restart tests on native platforms, and duplicate-launch plus persistence checks using the actual extracted archives. Build checks run on macOS 15 for Apple Silicon and Intel; these do not claim a Finder GUI test, native macOS 14.5 validation, Apple notarization or production certification.

Before updating, quit the known older VoteLab process. Do not delete voting.sqlite3 or its backups. If the old app is already working, continue at http://127.0.0.1:8765/ until ready to update.

## Previous release notes

# VoteLab 0.4.4 - Third trial feedback

������ʵ8�����÷����������ִν����󰴹���/���Լ������Զ����������������״��������״������ͳ��ͼ���������Ĭ��Ӣ�ģ�������ҳ�ʹ���ҳ�з�����ڣ����л��˺ţ�Ӣ����ʾͨ�����߷��������Ļ���ݣ�������ѡ���������򣻻ģ�������ʽ�İ���

- ���ؽ���������ݿ⡣������ȡԭ�û�����Ŀ¼������ǰ����SQLite���ݡ��ɻ�����Ըĳ��Զ������������߱༭�������ʹ�������á�
- ͳ��ͼ��ȡͬһ�ݼ�Ʊ����������ƹ������롢���������˽��Ȩ�ޡ�������Ϊ0-5ƽ���֣�δ���ֲ���0�֣���ʾ������RCV�ɲ鿴�����Ʊ���裬����̭�αװ����Ʊ��
- ������ѡ��һ����Ҫ��ѡʱ����ǰ�������ս����ƽƱ����Ʊ����ʾ��ȷ״̬��������ѡӮ�ҡ�
- ���߷���ֻ�ı���ʾ������ԭ�ġ��༭���ѡƱ���л��桢��ʱ���޶��Ӣ��ʧ����ʾ��MyMemoryΪ�ⲿ���񣬿�������򲻿��ã�����ÿ��5000�ַ����˺����ݡ����롢�ֻ��š������롢ͼƬ��ѡƱ���ύ���롣
- �л��˺Ž�������ǰ�Ự�����˺����ݼ������豸�Ự������������ѡ��̨��������ÿ��һ�

Addresses all eight trial items: automatic final-result publication or creator-only access, selectable charts, English default, return links, account switching, online English display translations, method-specific limits and formal template wording.

Existing data storage and startup backups are preserved. New PUBLIC events opt into automatic publication; untouched legacy settings remain manual. A majority round requiring a runoff is not published as the final result. Private and invitation-gated charts use the same permissions as the result table. Chart selection never changes votes.

Chinese visible activity text is translated through MyMemory (online, bounded timeouts, local cache, 5000-character daily anonymous allowance). Original records and editor fields remain intact. Source text is sent to an external service; use fictional non-sensitive activity content. Failure is labelled, with optional original-text viewing. No real SMS or permanent shared hosting is introduced.

Validation: regression tests plus isolated headless-browser checks for the eight changes, chart rendering, account switching, mobile layout and a synthetic live translation. Platform builds and package-restart persistence checks must pass before publication.

Reference: [MyMemory API](https://mymemory.translated.net/doc/spec.php), [usage limits](https://mymemory.translated.net/doc/usagelimits.php).

## Previous release notes

# VoteLab 0.4.3

�޸�������ѡ����ʾ��ÿ�����ѡ��������⡣�����������ڽ������ڵ�����ѡ��������ѡ��ȷ˵��ÿ��ÿ��ѡ1����Ʒ����һ�����˹���ʱ��ǰ��������ڶ�������ͶƱ�����ֺ�RCVҲ�������޹ص��������á��ɻ��ѡƱ�ɼ���ʹ�á�

Fixes the selection-limit field appearing for majority runoff. Only single/multiple choice uses the configurable limit. Majority runoff explains one choice per voter per round and a fresh top-two vote when nobody has a majority. Rating and RCV forms hide the irrelevant limit as well. Existing activities and ballots are retained.

## Included from 0.4.2

�����޸�ע�������ҳ����������⣬��������ҳչʾ��������ʾ���ṩ Windows x64��Mac Apple Silicon �� Mac Intel ��װ�������л��������ڰ��ڡ�

- ��ȡ��֤���Ϊ�ڵ�ǰҳ����ɡ������ڼ䱣�����ң��������ֻ��š��ƺ����������룬��ʾ����״̬�ͷ��ؽ����
- ����ʾ���롱���������ǩ��Ĭ�Ϲرգ��ɰ���Ҫ��ѡ��ע����������������˵��һ�¡�
- ���볤�����˼��һ�¡�����8��128���ַ���ע�������ʱ������������ͬ���ƺ����60���ַ����ֻ��Ű���ѡ���ң����������顣
- ��ҳʾ��ʹ����ȷ��ע�Ľ�����ʾͼ����ʵ���ѡƱ�ͽ��������ȡʵ�����ݿ⡣
- ����ơ���Ʒ���ƺͽ���ʹ�����Եı�����ʾ����㲻ͬ����Ļʹ�á�
- ���¼���ʹ��ԭ�����û�����Ŀ¼���������ݿ�����ǰ���ɾ��������Լ��� SQLite ���գ������˺š����ͼƬ��ѡƱ��¼��

ע���������ʹ��ҳ����ʾ����ʾ��֤�롣����ͶƱ��Ҫ�����˷�����֯���ṩ��ͬһ������ַ���������еı��ذ��ֱ𱣴����ϡ�Mac ԭ����������� macOS 15 �Ͻ��У�Mac ��δ���� Apple Developer ID ǩ���͹�֤���״�����ָ�������� READ ME FIRST.txt��

VoteLab 0.4.2 addresses registration and password-page feedback and improves homepage examples and form guidance. Downloads include their runtime for Windows x64, Mac Apple Silicon and Mac Intel.

- Verification-code requests complete on the current page, preserve form entries and show request feedback.
- Show password has a clear label, remains optional and starts unchecked.
- Passwords allow 8�C128 characters. Registration and reset require two matching entries. Display names allow up to 60 characters. Phone numbers follow the selected region's rules.
- Homepage examples are labelled interface illustrations. Actual activities, ballots and results use saved database records.
- Activity, entry and description fields use neutral prompts suited to different event topics.
- Updates reuse the existing user data directory. Startup snapshots of an existing SQLite database are integrity-checked and retain its accounts, activities, images and ballots.

Verification codes are local demonstrations displayed on screen. Shared voting uses one organiser-provided online URL. Local packages have separate data. Native Mac build checks run on macOS 15. The Mac app has no Apple Developer ID signature or notarization. The included READ ME FIRST.txt covers first-run instructions.

