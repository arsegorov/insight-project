These are the minimal steps

# IAM
* Create a group with AdministratorAccess policy (a built-in policy),
  say, `admins`.
* Create a user, say, `admin0`:
    * Add the user to the `admins` group.
    * Give the user **programmatic** access.
        * Download the `.csv` credentials file to a secure location, run
        ```shell
        $ chmod 400 <the .csv file>
        ```
        to prevent others from reading its contents.
    * You may also want to give the user the **AWS Management Console**
      (the web interface) access, since you shouldn't use the root user
      much, and you'd want to perform the remaining steps under a
      non-root user.
        * If you do that, make note of the login page link,
        and after you finish with creating the user,
        log out of **AWS Management Console** and log back in under
        the newly created user on the provided login page.

# S3
* Create a bucket,
  say, `s3-bucket`, (it should be a universally unique bucket name),
  so you'll probably need to be more creative.
  Keep it private (i.e., check all "Block public access..." checkboxes).

# VPC
* Create a VPC if doesn't exist, say, `vpc-0`. A /28-size CIDR block
  should suffice.
    * In the associated Security Group, say, `sg-0`,
      add these **inbound** rules:
  
      | Type       | Protocol | Port | Source                | Description  |
      | ---------- | -------- | ---- | --------------------- | ------------ |
      | Custom TCP | TPC      | 22   | My IP                 | \<any notes> |
      | Custom TCP | TPC      | 5432 | Custom (`vpc-0` CIDR) | \<any notes> |
      
        * **Custom TCP**, port 22, **My IP**.
          This allows SSH access from your local machine
        * **Custom TCP**, port 5432
          (unless you change the port when creating an RDS instance),
          enter the CIDR range associated with `vpc-0`.
          This allows the instances within your VPC to connect to the
          RDS database.
      
        
# EC2
* Create a `t2.micro` instance, say, `i-0`, using the `Ubuntu 18.04 LTS` AMI
  (not minimal). It can be found by searching `ubuntu` and selecting
  **Marketplace** (there will be  few hundred results,
  but this one should pretty close to the top)
    * Add to the existing security group, `sg-0`
    * Create a new key pair for ssh access,
      download the `.pem` key-pair file to a secure location, run
      ```shell
      $ chmod 400 <the .pem file>
      ```
      to prevent others from reading its contents
      (ssh also won't let you use this key pair later on
      if the permissions aren't set to owner-only access)
    * Create an Elastic IP, say, `eipalloc-0`, then associate it
      with the instance `i-0`. When this is done, you can ssh
      to that instance by running
      ```shell
      $ ssh ubuntu@<the elastic IP> -i <the .pem file>
      ```

# EC2 Instance
* ssh into the instance, and update ubuntu:
  ```shell
  $ sudo apt update
  $ sudo apt upgrade
  ```
* Install python3 and pip3:
  ```shell
  $ sudo apt python3, python3-pip
  ```
* Install `awscli`:
  ```shell
  $ pip3 install --user --upgrade awscli
  ```
  Log out of the instance and log back in for bash to locate `aws`
* You may want to install PostgreSQL CLI to test the instance's
  connection to the RDS later on:
  ```shell
  $ sudo apt install postgresql
  ```
    
# RDS
* Create a PostgreSQL database
    * Choose a name for the database instance and an admin user name
    * Choose `vpc-0` as the **VPC**
    * Choose the **default** Subnet
    * Choose **No** for public accessibility
    * Select **Choose existing VPC security groups**, then select **default**
    * Disable IAM DB authentication
    * Might need to grant RDS Service Linked Role some permissions in IAM
      to let it push logs to Cloud Watch
* After the instance is created, go to instance details and make note
  of the **Endpoint** in the **Connect** section. You'll use it to
  connect to your database.
  If you set up an inbound rule in your security group, `sg-0`,
  as described above, and installed PostgreSQL on your instance, `i-0`,
  you should be able to connect to your database on the database instance
  from `i-0`:
  ```shell
  $ psql -h '<endpoint from the DB`s Connect section>' \
         -p 5432 \
         -U '<DB admin user name>'
  ```
    * If you don't see any messages for a while, your security group's
      inbound rules probably haven't been set up properly
    * When you see the prompt, enter the DB user's password
    * You can also save the password in the `PGPASSWORD` environment
      variable, to avoid typing it in every time
      you connect. Add this line to the end of the `~/.bashrc` file:
      ```shell
      export PGPASSWORD='<DB user`s password>'
      ```
      Then run this from the command line:
      ```shell
      $ source ~/.bashrc
      ```
      