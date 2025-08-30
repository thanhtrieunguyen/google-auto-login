import os

def add_id_to_email(input_file='emails.txt', output_file='emails_with_id.txt'):
    with open(input_file, 'r', encoding='utf-8') as fin, open(output_file, 'w', encoding='utf-8') as fout:
        for line in fin:
            email = line.strip()
            if '@' in email:
                user = email.split('@')[0]
                fout.write(f'{email};{user}\n')
            else:
                fout.write(email + '\n')

if __name__ == '__main__':
    add_id_to_email() 